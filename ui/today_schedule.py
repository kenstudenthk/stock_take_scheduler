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
    total_shops = len(rows)
    groups = set(row["group_no"] for row in rows)
    num_groups = len(groups)
    
    col_sum1, col_sum2, col_sum3 = st.columns(3)
    with col_sum1:
        st.metric("Total shops today", total_shops)
    with col_sum2:
        st.metric("Number of groups", num_groups)
    with col_sum3:
        if rows[0].get("day_total_distance_km"):
            st.metric("Total distance (km)", f"{rows[0]['day_total_distance_km']:.1f}")
        else:
            st.metric("Total distance", "Not calculated")

    # ✅ Group by group_no and display
    for group_num in sorted(groups):
        group_rows = [r for r in rows if r["group_no"] == group_num]
        
        with st.expander(f"🗂️ Group {group_num} ({len(group_rows)} shops)", expanded=(group_num == 1)):
            for idx, r in enumerate(group_rows):
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
            all_groups = sorted(set(r.get("group_no", 1) for r in rows))
            selected_groups = st.multiselect(
                "Filter groups",
                all_groups,
                default=all_groups,
                format_func=lambda x: f"Group {x}",
            )
        

       
        # Create and display map
        deck = map_visualizer.create_route_map(
            rows,
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

    

def _render_row(idx: int, row: dict, group_num: int):
    """Render a single shop row with actions."""
    shop_id = row["shop_id"]
    route_order = row.get("day_route_order", 0)
    
    # ✅ Show route order number
    col_order, col_info, col_contact, col_actions = st.columns([0.5, 3, 2.5, 2])
    
    with col_order:
        st.markdown(f"### {route_order}")
        st.caption("Order")
    
    with col_info:
        st.markdown(
            f"**{shop_id} — {row['shop_name']}**\n\n"
            f"{row['address_zh']}"
        )
        
        status_emoji = {
            "Planned": "📅",
            "Done": "✅",
            "Closed": "🚫",
            "Rescheduled": "📆"
        }.get(row["status"], "❓")
        
        st.caption(
            f"{status_emoji} Status: **{row['status']}** | "
            f"Region: {row['region_code']} | "
            f"District: {row['district_en']}"
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
        if row["status"] == "Planned":
            done_key = f"done_{group_num}_{idx}"
            closed_key = f"closed_{group_num}_{idx}"
            resched_key = f"resched_{group_num}_{idx}"
            
            if st.button("✅ Done", key=done_key, use_container_width=True):
                st.session_state["action"] = ("done", shop_id)
                st.session_state["action_date"] = row["date"]
                st.rerun()
            
            if st.button("🚫 Closed", key=closed_key, use_container_width=True):
                st.session_state["action"] = ("closed", shop_id)
                st.session_state["action_date"] = row["date"]
                st.rerun()
            
            if st.button("📆 Reschedule", key=resched_key, use_container_width=True):
                st.session_state["action"] = ("resched", shop_id)
                st.session_state["action_date"] = row["date"]
                st.rerun()
        else:
            st.caption(f"Status: {row['status']}")
    
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



