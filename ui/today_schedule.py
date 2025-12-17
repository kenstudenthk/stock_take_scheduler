# ui/today_schedule.py

import streamlit as st
import pandas as pd
from datetime import date, timedelta
from core import data_access, holidays
from core import folium_map
from streamlit_folium import st_folium
import folium


def render():
    """Render the Today Schedule page with new 2-column layout."""
    
    st.subheader("📅 Today's Schedule")
    
    # ========== Top Filter Bar (緊湊型) ==========
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
    col_left, col_right = st.columns([0.30, 0.70])
    
    # ---------- LEFT COLUMN: Shop List by Group ----------
    with col_left:
        st.markdown("#### 📝 Today's Route")
        
        # Group colors (high contrast)
        GROUP_COLORS = {
            1: "#FF6B6B",  # Red
            2: "#4ECDC4",  # Cyan
            3: "#45B7D1",  # Blue
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
                
                # Shop Card
                with st.container():
                    c_logo, c_main, c_action = st.columns([0.8, 3.0, 1.2])
                    
                    with c_logo:
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
                    
                    with c_main:
                        st.markdown(
                            f"""
                            <div style='padding-top: 2px;'>
                                <div style='font-size: 13px; font-weight: 600; color: #111827; margin-bottom: 2px;'>
                                    {shop_name}
                                </div>
                                <div style='font-size: 11px; color: #6b7280;'>
                                    {shop_id} · {brand}
                                </div>
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                    
                    with c_action:
                        # Status badge
                        status_config = {
                            "Done": {"color": "#22c55e", "icon": "✓"},
                            "Closed": {"color": "#ef4444", "icon": "✕"},
                            "Rescheduled": {"color": "#f97316", "icon": "↻"},
                            "Planned": {"color": "#3b82f6", "icon": "○"}
                        }
                        
                        s_conf = status_config.get(status, status_config["Planned"])
                        
                        st.markdown(
                            f"""
                            <div style='
                                font-size: 11px;
                                font-weight: 600;
                                background-color: {s_conf['color']}15;
                                color: {s_conf['color']};
                                padding: 4px 8px;
                                border-radius: 12px;
                                text-align: center;
                                border: 1px solid {s_conf['color']}40;
                            '>
                                {s_conf['icon']} {status}
                            </div>
                            """,
                            unsafe_allow_html=True
                        )
                
                # Spacing between cards
                st.markdown("<div style='height: 6px;'></div>", unsafe_allow_html=True)
            
            # Spacing between groups
            st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
    
    # ---------- RIGHT COLUMN: Map with Tooltip ----------
    with col_right:
        st.markdown("#### 🗺️ Route Map")
        
        try:
            # Create Folium map
            folium_map_obj = folium_map.create_route_map_folium(
                schedule_data=filtered_data,
                date_str=selected_date.isoformat(),
                show_route_lines=True,
                selected_groups=selected_groups
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


# Helper functions for marking status (keep existing)
def _mark_as_done(shop_id: str, date_str: str):
    """Mark shop as done."""
    try:
        data_access.update_shop_status(shop_id, date_str, "Done")
        st.success(f"✅ Marked {shop_id} as Done")
        st.rerun()
    except Exception as e:
        st.error(f"Error: {e}")


def _show_closed_confirmation(shop_id: str, shop_name: str, date_str: str):
    """Show confirmation dialog for marking as closed."""
    st.session_state[f"confirm_closed_{shop_id}_{date_str}"] = True


def _show_reschedule_dialog(shop_id: str, shop_name: str, date_str: str):
    """Show reschedule dialog."""
    st.session_state[f"reschedule_{shop_id}_{date_str}"] = True
