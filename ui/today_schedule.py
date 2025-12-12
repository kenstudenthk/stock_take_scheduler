# ui/today_schedule.py
import datetime
import streamlit as st
import sqlite3
from core import data_access, holidays


def _get_max_shops_per_day() -> int:
    """Get maximum shops per day from settings."""
    val = data_access.get_setting("shops_per_day", "20")
    try:
        return int(val)
    except ValueError:
        return 20


def _find_next_available_date(
    start_date: datetime.date,
    max_days: int = 14,
) -> datetime.date | None:
    """Find the next available business day with capacity."""
    max_per_day = _get_max_shops_per_day()
    d = start_date + datetime.timedelta(days=1)
    
    for _ in range(max_days):
        if not holidays.is_business_day(d):
            d += datetime.timedelta(days=1)
            continue
        
        count = data_access.count_shops_on_date(d.isoformat())
        if count < max_per_day:
            return d
        
        d += datetime.timedelta(days=1)
    
    return None


def render():
    st.subheader("Today Schedule")

    # Date picker
    default_date = datetime.date.today()
    selected_date = st.date_input(
        "Select date to view schedule",
        value=default_date,
        help="Pick any date to view its schedule.",
    )

    # Monthly summary
    summary = data_access.get_month_summary(selected_date.year, selected_date.month)
    
    st.markdown("### Monthly summary")
    s_col1, s_col2, s_col3, s_col4, s_col5 = st.columns(5)
    
    with s_col1:
        st.metric("Total visits", summary["Total"])
    with s_col2:
        st.metric("Planned", summary["Planned"])
    with s_col3:
        st.metric("Done", summary["Done"])
    with s_col4:
        st.metric("Closed", summary["Closed"])
    with s_col5:
        st.metric("Rescheduled", summary["Rescheduled"])

    st.caption(
        f"Summary for {selected_date.year}-{selected_date.month:02d} "
        "(based on schedule table)."
    )

    st.markdown("---")
    st.markdown(f"### Schedule for {selected_date.isoformat()}")

     # Handle actions first
    _handle_actions(selected_date)

    # ✅ Load schedule with proper ordering by group and route order
    with data_access.get_db_connection() as conn:
        conn.row_factory = sqlite3.Row  # 確保可以轉成 dict
        cur = conn.cursor()
        
        # 注意：cur.execute 必須在 with 區塊的縮排內執行
        cur.execute(
            """
            SELECT *
            FROM schedule s
            JOIN shop_master sm ON s.shop_id = sm.shop_id
            WHERE s.date = ? 
            """,
            (selected_date.isoformat(),)
        )

        
        # fetchall 也要在 with 區塊內
        rows = cur.fetchall()

    # --- 以下跳出 with 區塊，conn 已經自動關閉，但 rows 資料已經拿到了 ---

    if not rows:
        st.info("今天沒有排程。 (No schedule for today)")
        return

    # 轉成 dict list
    data = [dict(row) for row in rows]
    
    # 3. 在 Python 層面處理欄位名稱 (容錯)
    for d in data:
        d['lat'] = d.get('lat') or d.get('Latitude') or d.get('field_20')
        d['lng'] = d.get('lng') or d.get('Longitude') or d.get('field_21')
        d['region'] = d.get('region_code') or d.get('Region')
        d['contact'] = d.get('contact_name') or d.get('ContactName')

    # ... 接下來繼續你的程式碼 ...


    # ✅ Show summary for this day
    total_shops = len(data)  # 改用 data
    
    # 使用 data 來計算 groups (注意：要處理 group_no 可能是 None 的情況)
    groups = set(d.get("group_no") for d in data if d.get("group_no") is not None)
    num_groups = len(groups)
    
    col_sum1, col_sum2, col_sum3 = st.columns(3)
    with col_sum1:
        st.metric("Total shops today", total_shops)
    with col_sum2:
        st.metric("Number of groups", num_groups)
    with col_sum3:
        if data and data[0].get("day_total_distance_km"):
             # 小心：如果值是字串，這裡可能要 float() 轉型，或者直接印出
             val = data[0]['day_total_distance_km']
             try:
                 st.metric("Total distance (km)", f"{float(val):.1f}")
             except:
                 st.metric("Total distance (km)", str(val))
        else:
            st.metric("Total distance", "Not calculated")

    # ✅ Group by group_no and display
    for group_num in sorted(groups):
        # 1. 先從 data (已經轉成 dict list) 裡篩選出屬於該群組的資料
        group_data = [d for d in data if d.get("group_no") == group_num]
        
        with st.expander(f"🗂️ Group {group_num} ({len(group_data)} shops)", expanded=(group_num == 1)):
            # 2. 只遍歷該群組的資料
            for idx, r in enumerate(group_data):
                # 3. 呼叫渲染函式
                # 這裡的 idx 是該群組內的索引，key = group_num + unique_id + idx，絕對唯一
                _render_row(idx, r, group_num)


  # ui/today_schedule.py
# 在現有程式碼最後加入以下內容

    # ================================
    # 🗺️ Interactive Map Section ONLY
    # ================================
    
    if rows:
        st.markdown("---")
        st.markdown("### 🗺️ Interactive Route Map")
        
        from core import map_visualizer
        
        # Map controls in a more compact layout
        col_ctrl1, col_ctrl2, col_ctrl3, col_ctrl4 = st.columns([1, 1, 1, 2])
        
        with col_ctrl1:
            show_lines = st.checkbox("Show route lines", value=True)
        
        with col_ctrl2:
            show_labels = st.checkbox("Show route numbers", value=True)
        
        with col_ctrl3:
            map_style = st.selectbox(
                "Map style",
                ["light", "dark", "streets", "satellite"],
                index=0,
            )
        
        with col_ctrl4:
            # Get all groups
            all_groups = sorted(set(d.get("group_no", 1) for d in data))
            selected_groups = st.multiselect(
                "Filter groups",
                all_groups,
                default=all_groups,
                format_func=lambda x: f"Group {x}",
            )
        

       
        # Create and display map
        deck = map_visualizer.create_route_map(
            data,
            selected_date.isoformat(),
            show_route_lines=show_lines,
            show_labels=show_labels,
            selected_groups=selected_groups if selected_groups else None,
            map_style=map_style,
        )
        
        if deck:
            st.pydeck_chart(deck, use_container_width=True)
        else:
            st.warning("⚠️ No location data available for mapping.")

    

def _render_row(idx, row, group_num):
    # 1. 補上變數定義 (從 row 取值)
    shop_id = row.get("shop_id", "Unknown")
    route_order = row.get("day_route_order", idx + 1)
    
    # 2. 獲取唯一識別碼 (優先用 schedule_id)
    unique_id = row.get("schedule_id") or shop_id or idx
    
    # 3. 建立唯一的 key (包含 group_num 避免跨群組衝突)
    # 統一在這裡定義，下面直接用
    done_key = f"btn_done_{group_num}_{unique_id}_{idx}"
    closed_key = f"btn_closed_{group_num}_{unique_id}_{idx}"
    resched_key = f"btn_resched_{group_num}_{unique_id}_{idx}"
    
    # ✅ Show route order number
    col_order, col_info, col_contact, col_actions = st.columns([0.5, 3, 2.5, 2])
    
    with col_order:
        st.markdown(f"### {route_order}")
        st.caption("Order")
    
    with col_info:
        # 使用 .get 避免 KeyError
        shop_name = row.get('shop_name', 'Unknown Shop')
        address = row.get('address_zh', '')
        
        st.markdown(
            f"**{shop_id} — {shop_name}**\n\n"
            f"{address}"
        )
        
        status = row.get("status", "Planned")
        status_emoji = {
            "Planned": "📅",
            "Done": "✅",
            "Closed": "🚫",
            "Rescheduled": "📆"
        }.get(status, "❓")
        
        region = row.get('region_code', '-')
        district = row.get('district_en', '-')
        
        st.caption(
            f"{status_emoji} Status: **{status}** | "
            f"Region: {region} | "
            f"District: {district}"
        )
        
        # ✅ Show coordinates if available
        if row.get("lat") and row.get("lng"):
            st.caption(f"📍 Location: {row['lat']:.4f}, {row['lng']:.4f}")
    
    with col_contact:
        brand = row.get("brand", "")
        phone = row.get("phone", "")
        contact = row.get("contact_name", "")
        
        lines = []
        if brand:
            lines.append(f"🏢 Brand: {brand}")
        if phone:
            lines.append(f"📞 Phone: {phone}")
        if contact:
            lines.append(f"👤 Contact: {contact}")
        
        if lines:
            st.markdown("\n\n".join(lines))
        else:
            st.caption("No contact info")
    
    with col_actions:
        # ✅ Only show actions if status is Planned
        if status == "Planned":
            # 直接使用上面定義好的 key
            if st.button("✅ Done", key=done_key, use_container_width=True):
                st.session_state["action"] = ("done", shop_id)
                st.session_state["action_date"] = row.get("date")
                st.rerun()
            
            if st.button("🚫 Closed", key=closed_key, use_container_width=True):
                st.session_state["action"] = ("closed", shop_id)
                st.session_state["action_date"] = row.get("date")
                st.rerun()
            
            if st.button("📆 Reschedule", key=resched_key, use_container_width=True):
                st.session_state["action"] = ("resched", shop_id)
                st.session_state["action_date"] = row.get("date")
                st.rerun()
        else:
            st.caption(f"Status: {status}")
    
    st.divider()



def _handle_actions(selected_date: datetime.date):
    """Handle button actions (Done, Closed, Reschedule)."""
    action_info = st.session_state.get("action")
    action_date = st.session_state.get("action_date")
    
    if not action_info or not action_date:
        return
    
    action, shop_id = action_info
    
    # Only apply if the action is for the selected date
    if action_date != selected_date.isoformat():
        st.session_state.pop("action", None)
        st.session_state.pop("action_date", None)
        return
    
    try:
        if action == "done":
            data_access.update_schedule_status(
                selected_date.isoformat(),
                shop_id,
                "Done",
                None,
            )
            st.success(f"✅ Marked {shop_id} as Done.")
        
        elif action == "closed":
            data_access.update_schedule_status(
                selected_date.isoformat(),
                shop_id,
                "Closed",
                "Permanent closure",
            )
            data_access.mark_shop_permanently_closed(shop_id)
            st.warning(f"🚫 Marked {shop_id} as Closed (permanent).")
            
            # ✅ Clear holidays cache if shop data changed
            holidays.clear_holidays_cache()
        
        elif action == "resched":
            new_date = _find_next_available_date(selected_date, max_days=14)
            
            if new_date is None:
                st.error("❌ No available date within next 14 days for re-schedule.")
            else:
                data_access.move_schedule_to_new_date(
                    selected_date.isoformat(),
                    new_date.isoformat(),
                    shop_id,
                )
                st.info(f"📆 Re-scheduled {shop_id} to {new_date.isoformat()}.")
    
    except Exception as e:
        st.error(f"Error performing action: {str(e)}")
    
    finally:
        # Clear action so it does not repeat
        st.session_state.pop("action", None)
        st.session_state.pop("action_date", None)



