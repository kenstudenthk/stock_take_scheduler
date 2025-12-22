# ui/today_schedule.py

import streamlit as st
import pandas as pd
from datetime import date, timedelta
from core import data_access, holidays
from core import folium_map
from streamlit_folium import st_folium
import folium


def render():
    """Render the Today Schedule page with action buttons."""
    
    st.subheader("📅 Today's Schedule")
    
    # ========== Top Filter Bar ==========
    filter_col1, filter_col2, filter_col3 = st.columns([1.5, 2, 3])
    
    with filter_col1:
        selected_date = st.date_input(
            "📅 Date",
            value=date.today(),
            key="today_schedule_date",
            label_visibility="collapsed"
        )
    
    # Get schedule for selected date
    schedule_data = data_access.get_schedule_by_date(selected_date.isoformat())
    
    if not schedule_data:
        st.info(f"📭 No schedule found for {selected_date.strftime('%Y-%m-%d')}")
        st.info("💡 Go to 'Generate Schedule' tab to create a new schedule")
        return
    
    # Convert to DataFrame
    df = pd.DataFrame(schedule_data)
    
    # Get unique groups
    unique_groups = sorted(df['group_number'].unique())
    
    with filter_col2:
        selected_groups = st.multiselect(
            "👥 Groups",
            options=unique_groups,
            default=unique_groups,
            key="today_groups_filter",
            label_visibility="collapsed",
            placeholder="Select groups..."
        )
    
    with filter_col3:
        st.markdown(
            f"""
            <div style='padding: 8px 12px; background-color: #f0f9ff; border-radius: 6px; 
                        border-left: 3px solid #3b82f6; margin-top: 6px;'>
                <span style='font-size: 14px; font-weight: 600; color: #1e40af;'>
                    📊 Total: {len(df)} shops in {len(unique_groups)} groups
                </span>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    # Filter data by selected groups
    if selected_groups:
        filtered_data = [s for s in schedule_data if s.get('group_number') in selected_groups]
        df_filtered = df[df['group_number'].isin(selected_groups)]
    else:
        filtered_data = schedule_data
        df_filtered = df
    
    st.markdown("<div style='margin-top: 20px;'></div>", unsafe_allow_html=True)
    
    # ========== Main Layout: Left Shop List + Right Map ==========
    col_left, col_right = st.columns([0.35, 0.65])
    
    # ---------- LEFT COLUMN: Shop List by Group ----------
    with col_left:
        st.markdown("#### 📝 Today's Route")
        
        # Group colors (high contrast)
        GROUP_COLORS = {
            1: "#FF6B6B",  # Red
            2: "#10B981",  # Green
            3: "#FBBF24",  # Yellow
        }
        
        df_sorted = df_filtered.sort_values(["group_number", "shop_id"])
        
        for group_no in selected_groups:
            group_df = df_sorted[df_sorted["group_number"] == group_no]
            
            if group_df.empty:
                continue
            
            group_color = GROUP_COLORS.get(group_no, "#95A5A6")
            
            # Group Header
            st.markdown(
                f"""
                <div style='
                    display: flex;
                    align-items: center;
                    justify-content: space-between;
                    background: linear-gradient(135deg, {group_color}15 0%, {group_color}05 100%);
                    padding: 10px 12px;
                    border-radius: 8px;
                    border-left: 4px solid {group_color};
                    margin-bottom: 8px;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
                '>
                    <div>
                        <div style='font-weight: 600; font-size: 14px; color: #1f2937;'>
                            Group {group_no}
                        </div>
                        <div style='font-size: 12px; color: #6b7280;'>
                            {len(group_df)} shops
                        </div>
                    </div>
                    <div style='
                        width: 36px; height: 36px;
                        background-color: {group_color};
                        border-radius: 50%;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        color: white;
                        font-weight: 700;
                        font-size: 16px;
                    '>
                        {group_no}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
            
            # Shops in this group
            for idx, row in group_df.iterrows():
                logo_url = row.get("brand_icon_url", "")
                shop_id = row["shop_id"]
                shop_name = row["shop_name"]
                brand = row["brand"]
                address = row["address"]
                status = row.get("status", "Planned")
                
                # ========== Shop Card with Expandable Actions ==========
                with st.expander(
                    f"**{shop_name}** · {shop_id}",
                    expanded=False
                ):
                    # Shop Info
                    info_col1, info_col2 = st.columns([0.15, 0.85])
                    
                    with info_col1:
                        if logo_url and isinstance(logo_url, str) and logo_url.startswith("http"):
                            try:
                                st.image(logo_url, width=40)
                            except:
                                st.markdown(
                                    f"<div style='width:40px;height:40px;background:#e5e7eb;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:12px;color:#6b7280;font-weight:600;'>{brand[:2]}</div>",
                                    unsafe_allow_html=True
                                )
                        else:
                            st.markdown(
                                f"<div style='width:40px;height:40px;background:#e5e7eb;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:12px;color:#6b7280;font-weight:600;'>{brand[:2]}</div>",
                                unsafe_allow_html=True
                            )
                    
                    with info_col2:
                        st.markdown(f"**Brand:** {brand}")
                        st.markdown(f"**Address:** {address}")
                        st.markdown(f"**Status:** `{status}`")
                    
                    st.markdown("---")
                    
                    # ✅ Action Buttons
                    btn_col1, btn_col2, btn_col3 = st.columns(3)
                    
                    with btn_col1:
                        if st.button(
                            "✅ Done",
                            key=f"done_{shop_id}_{selected_date}",
                            use_container_width=True,
                            type="primary" if status != "Done" else "secondary",
                            disabled=(status == "Done")
                        ):
                            if _mark_as_done(shop_id, selected_date.isoformat()):
                                st.rerun()
                    
                    with btn_col2:
                        # ✅ 根據狀態改變按鈕文字和樣式
                        is_closed = (status == "Closed")
                        button_text = "🔓 Reopen" if is_closed else "🚫 Closed"
                        button_type = "secondary" if is_closed else "primary"
                        
                        if st.button(
                            button_text,
                            key=f"closed_{shop_id}_{selected_date}",
                            use_container_width=True,
                            type=button_type
                        ):
                            st.session_state[f"confirm_closed_{shop_id}"] = True
                            st.rerun()
                    
                    with btn_col3:
                        if st.button(
                            "📅 Reschedule",
                            key=f"reschedule_{shop_id}_{selected_date}",
                            use_container_width=True,
                            disabled=(status == "Rescheduled")
                        ):
                            st.session_state[f"show_reschedule_{shop_id}"] = True
                            st.rerun()
                    
                    # ✅ Closed/Reopen Confirmation Dialog
                    if st.session_state.get(f"confirm_closed_{shop_id}", False):
                        st.markdown("---")
                        
                        is_closed = (status == "Closed")
                        
                        if is_closed:
                            # 如果已經關閉，顯示取消關閉的確認
                            st.info(f"ℹ️ **Confirm to reopen '{shop_name}'?**")
                            st.caption("This action will change the shop status back to 'Planned' and it will appear in schedules again.")
                            
                            confirm_col1, confirm_col2 = st.columns(2)
                            
                            with confirm_col1:
                                if st.button(
                                    "✅ Confirm Reopen", 
                                    key=f"confirm_reopen_yes_{shop_id}", 
                                    use_container_width=True,
                                    type="primary"
                                ):
                                    if _reopen_shop(shop_id, selected_date.isoformat(), shop_name):
                                        st.session_state[f"confirm_closed_{shop_id}"] = False
                                        st.rerun()
                            
                            with confirm_col2:
                                if st.button(
                                    "❌ Cancel", 
                                    key=f"confirm_reopen_no_{shop_id}", 
                                    use_container_width=True
                                ):
                                    st.session_state[f"confirm_closed_{shop_id}"] = False
                                    st.rerun()
                        else:
                            # 如果未關閉,顯示關閉的確認
                            st.warning(f"⚠️ **Confirm that '{shop_name}' is permanently closed?**")
                            st.caption("This action will mark the shop as closed and it will not appear in future schedules.")
                            
                            confirm_col1, confirm_col2 = st.columns(2)
                            
                            with confirm_col1:
                                if st.button(
                                    "✅ Confirm Closed", 
                                    key=f"confirm_closed_yes_{shop_id}", 
                                    use_container_width=True,
                                    type="primary"
                                ):
                                    if _mark_as_closed(shop_id, selected_date.isoformat(), shop_name):
                                        st.session_state[f"confirm_closed_{shop_id}"] = False
                                        st.rerun()
                            
                            with confirm_col2:
                                if st.button(
                                    "❌ Cancel", 
                                    key=f"confirm_closed_no_{shop_id}", 
                                    use_container_width=True
                                ):
                                    st.session_state[f"confirm_closed_{shop_id}"] = False
                                    st.rerun()
                    
                    # Reschedule Dialog
                    if st.session_state.get(f"show_reschedule_{shop_id}", False):
                        st.markdown("---")
                        st.markdown("##### 📅 Reschedule to:")
                        new_date = st.date_input(
                            "New Date",
                            value=selected_date + timedelta(days=7),
                            key=f"new_date_{shop_id}",
                            min_value=date.today()
                        )
                        
                        reschedule_col1, reschedule_col2 = st.columns(2)
                        
                        with reschedule_col1:
                            if st.button("✅ Confirm", key=f"confirm_reschedule_{shop_id}", use_container_width=True, type="primary"):
                                if _reschedule_shop(shop_id, selected_date.isoformat(), new_date.isoformat()):
                                    st.session_state[f"show_reschedule_{shop_id}"] = False
                                    st.rerun()
                        
                        with reschedule_col2:
                            if st.button("❌ Cancel", key=f"cancel_reschedule_{shop_id}", use_container_width=True):
                                st.session_state[f"show_reschedule_{shop_id}"] = False
                                st.rerun()
                
                # Spacing between cards
                st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)
            
            # Spacing between groups
            st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
    
    # ---------- RIGHT COLUMN: Map with Tooltip ----------
    # 在 with col_right: 區塊內，地圖標題後添加

    with col_right:
        # ✅ 地圖標題與樣式選擇器在同一行
        map_header_col1, map_header_col2 = st.columns([0.6, 0.4])
        
        with map_header_col1:
            st.markdown("#### 🗺️ Route Map")
        
        with map_header_col2:
            map_style = st.selectbox(
                "🎨 Map Style",
                options=["Light", "Dark", "Standard", "Terrain", "Toner", "Watercolor"],
                index=0,  # 預設 Light
                key="map_style_selector",
                label_visibility="collapsed"
            )
        
        try:
            # Create Folium map with selected style
            folium_map_obj = folium_map.create_route_map_folium(
                schedule_data=filtered_data,
                date_str=selected_date.isoformat(),
                show_route_lines=True,
                selected_groups=selected_groups,
                map_style=map_style  # ✅ 傳遞選擇的樣式
            )
            
            # Display map
            st_folium(
                folium_map_obj,
                width=None,
                height=650,
                returned_objects=[]
            )
            
        except Exception as e:
            st.error(f"❌ Map display error: {e}")
            import traceback
            st.code(traceback.format_exc())


# ========== Helper Functions ==========

def _mark_as_done(shop_id: str, date_str: str) -> bool:
    """Mark shop as Done."""
    try:
        success = data_access.update_schedule_status(shop_id, date_str, "Done")
        if success:
            st.success(f"✅ Marked {shop_id} as Done")
            return True
        else:
            st.error(f"❌ Failed to update {shop_id}")
            return False
    except Exception as e:
        st.error(f"Error: {e}")
        return False


def _mark_as_closed(shop_id: str, date_str: str, shop_name: str = "") -> bool:
    """Mark shop as Closed."""
    try:
        success = data_access.update_schedule_status(shop_id, date_str, "Closed")
        if success:
            st.success(f"🚫 '{shop_name}' ({shop_id}) marked as Closed")
            return True
        else:
            st.error(f"❌ Failed to update {shop_id}")
            return False
    except Exception as e:
        st.error(f"Error: {e}")
        return False


def _reopen_shop(shop_id: str, date_str: str, shop_name: str = "") -> bool:
    """Reopen a closed shop (change status from Closed to Planned)."""
    try:
        success = data_access.update_schedule_status(shop_id, date_str, "Planned")
        if success:
            st.success(f"✅ '{shop_name}' ({shop_id}) has been reopened and set to Planned")
            return True
        else:
            st.error(f"❌ Failed to reopen {shop_id}")
            return False
    except Exception as e:
        st.error(f"Error: {e}")
        return False


def _reschedule_shop(shop_id: str, old_date: str, new_date: str) -> bool:
    """Reschedule shop to a new date."""
    try:
        # Get shop data from old schedule
        with data_access.get_db_connection() as conn:
            cur = conn.cursor()
            
            cur.execute("""
                SELECT shop_id, shop_name, address, region, district,
                       brand, lat, lng, is_mtr, group_number
                FROM schedule
                WHERE shop_id = ? AND schedule_date = ?
            """, (shop_id, old_date))
            
            row = cur.fetchone()
            
            if not row:
                st.error(f"❌ Shop {shop_id} not found in schedule")
                return False
            
            # Mark old schedule as Rescheduled
            cur.execute("""
                UPDATE schedule
                SET status = 'Rescheduled'
                WHERE shop_id = ? AND schedule_date = ?
            """, (shop_id, old_date))
            
            # Insert into new date
            cur.execute("""
                INSERT INTO schedule (
                    shop_id, shop_name, address, region, district,
                    brand, lat, lng, is_mtr, schedule_date, group_number, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Planned')
            """, (
                row[0], row[1], row[2], row[3], row[4],
                row[5], row[6], row[7], row[8], new_date, row[9]
            ))
            
            conn.commit()
        
        st.success(f"✅ Rescheduled {shop_id} to {new_date}")
        return True
        
    except Exception as e:
        st.error(f"❌ Reschedule failed: {e}")
        import traceback
        st.code(traceback.format_exc())
        return False
