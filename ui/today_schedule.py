# ui/today_schedule.py

import streamlit as st
import pandas as pd
from datetime import date, timedelta
from core import data_access, holidays, map_visualizer


def render():
    """Render the Today Schedule page."""
    st.subheader("📅 Today's Schedule")
    
    # Date selector
    col_date, col_groups = st.columns([2, 3])
    
    with col_date:
        selected_date = st.date_input(
            "Select date to view schedule",
            value=date.today(),
            key="today_schedule_date"
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
    
    with col_groups:
        selected_groups = st.multiselect(
            "Filter by Groups",
            options=unique_groups,
            default=unique_groups,
            key="today_groups_filter"
        )
    
    # Filter data by selected groups
    if selected_groups:
        filtered_data = [s for s in schedule_data if s.get('group_number') in selected_groups]
    else:
        filtered_data = schedule_data
    
    st.markdown(f"### 📊 Total: {len(filtered_data)} shops in {len(selected_groups) if selected_groups else len(unique_groups)} groups")
    
    # ========== MAP DISPLAY ==========
    st.markdown("### 🗺️ Route Map")
    
    try:
        deck = map_visualizer.create_route_map(
            schedule_data=filtered_data,
            date_str=selected_date.isoformat(),
            show_route_lines=True,
            show_labels=True,
            selected_groups=selected_groups,
            map_style="light"
        )
        
        if deck:
            st.pydeck_chart(deck, use_container_width=True)
        else:
            st.warning("⚠️ No map data available")
    except Exception as e:
        st.error(f"❌ Map display error: {e}")
        import traceback
        st.code(traceback.format_exc())
    
    st.markdown("---")
    
    # ========== SHOP LIST BY GROUP ==========
    df_filtered = df[df['group_number'].isin(selected_groups)] if selected_groups else df
    groups = df_filtered.groupby("group_number")
    
    for group_num, group_df in groups:
        with st.expander(f"🏪 Group {group_num} ({len(group_df)} shops)", expanded=True):
            
            for idx, row in group_df.iterrows():
                col_logo, col1, col2, col3 = st.columns([0.8, 2.2, 1, 1])  # ✅ 增加 Logo 欄位寬度
                
                with col_logo:
                    # Display brand logo
                    logo_url = row.get('brand_icon_url', '')
                    if logo_url and logo_url.startswith('http'):
                        try:
                            st.image(logo_url, width=80)  # ✅ 從 40 增加到 80
                        except:
                            st.markdown("🏪")
                    else:
                        st.markdown("🏪")

                
                with col1:
                    # Shop info
                    st.markdown(f"**{row['shop_name']}** ({row['shop_id']})")
                    st.caption(f"📍 {row['address']} | 🏢 {row['brand']}")
                
                with col2:
                    # Status indicator
                    status = row.get('status', 'Planned')
                    if status == 'Done':
                        st.success("✅ Done")
                    elif status == 'Closed':
                        st.error("🚫 Closed")
                    elif status == 'Rescheduled':
                        st.warning("📅 Rescheduled")
                    else:
                        st.info("📋 Planned")
                
                with col3:
                    # Action buttons
                    if status != 'Done' and status != 'Closed':
                        if st.button("✅", key=f"done_{row['shop_id']}_{selected_date}", help="Mark as Done"):
                            _mark_as_done(row['shop_id'], selected_date.isoformat())
                        
                        if st.button("🚫", key=f"closed_{row['shop_id']}_{selected_date}", help="Mark as Closed"):
                            _show_closed_confirmation(row['shop_id'], row['shop_name'], selected_date.isoformat())
                        
                        if st.button("📅", key=f"reschedule_{row['shop_id']}_{selected_date}", help="Reschedule"):
                            _show_reschedule_dialog(row['shop_id'], row['shop_name'], selected_date.isoformat())


def _mark_as_done(shop_id: str, schedule_date: str):
    """Mark a shop as Done."""
    try:
        data_access.update_schedule_status(schedule_date, shop_id, "Done", None)
        st.success(f"✅ Marked {shop_id} as Done.")
        _sync_to_sharepoint(shop_id, "Done")
        st.rerun()
    except Exception as e:
        st.error(f"❌ Failed: {str(e)}")


def _show_closed_confirmation(shop_id: str, shop_name: str, schedule_date: str):
    """Show confirmation dialog for marking shop as Closed."""
    @st.dialog(f"🚫 Confirm Closure", width="large")
    def confirm_closed():
        st.warning("⚠️ **Warning: This will mark the shop as permanently closed**")
        
        st.markdown(f"""
        **Shop Information:**
        - Shop ID: `{shop_id}`
        - Shop Name: {shop_name}
        - Schedule Date: {schedule_date}
        
        ---
        
        **Confirm this shop is permanently closed?**
        - This shop will be removed from future schedules
        - Status will be synced to SharePoint List
        """)
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("✅ Yes, Confirm", type="primary", use_container_width=True):
                try:
                    data_access.update_schedule_status(schedule_date, shop_id, "Closed", None)
                    
                    with data_access.get_db_connection() as conn:
                        cur = conn.cursor()
                        cur.execute("UPDATE shop_master SET is_active = 'N' WHERE shop_id = ?", (shop_id,))
                    
                    st.success(f"✅ Marked {shop_id} as Closed")
                    _sync_to_sharepoint(shop_id, "Closed")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Failed: {str(e)}")
        
        with col2:
            if st.button("❌ Cancel", use_container_width=True):
                st.rerun()
    
    confirm_closed()


def _show_reschedule_dialog(shop_id: str, shop_name: str, original_date: str):
    """Show reschedule dialog."""
    @st.dialog(f"📅 Reschedule: {shop_name}", width="large")
    def reschedule_dialog():
        st.markdown(f"""
        **Shop Information:**
        - Shop ID: `{shop_id}`
        - Shop Name: {shop_name}
        - Original Date: {original_date}
        """)
        
        st.markdown("---")
        
        suggested_date = _get_next_available_date(original_date)
        st.info(f"💡 **Suggested date: {suggested_date.strftime('%Y-%m-%d (%A)')}**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button(f"✅ Accept\n{suggested_date.strftime('%Y-%m-%d')}", type="primary", use_container_width=True):
                _perform_reschedule(shop_id, original_date, suggested_date.isoformat())
        
        with col2:
            if st.button("📆 Manual Date", use_container_width=True):
                st.session_state['show_manual_date'] = True
                st.rerun()
        
        if st.session_state.get('show_manual_date', False):
            st.markdown("---")
            manual_date = st.date_input("Select new date", value=suggested_date, min_value=date.today())
            
            if holidays.is_holiday(manual_date.isoformat()):
                st.warning(f"⚠️ {manual_date.strftime('%Y-%m-%d')} is a public holiday")
            
            col_confirm, col_cancel = st.columns(2)
            
            with col_confirm:
                if st.button("✅ Confirm", type="primary", use_container_width=True):
                    _perform_reschedule(shop_id, original_date, manual_date.isoformat())
            
            with col_cancel:
                if st.button("❌ Cancel", use_container_width=True):
                    st.session_state['show_manual_date'] = False
                    st.rerun()
    
    reschedule_dialog()


def _get_next_available_date(original_date: str) -> date:
    """Calculate next available date."""
    from datetime import datetime
    
    current = datetime.fromisoformat(original_date).date()
    next_date = current + timedelta(days=1)
    
    max_attempts = 30
    attempts = 0
    
    while attempts < max_attempts:
        if next_date.weekday() >= 5:
            next_date += timedelta(days=1)
            attempts += 1
            continue
        
        if holidays.is_holiday(next_date.isoformat()):
            next_date += timedelta(days=1)
            attempts += 1
            continue
        
        existing = data_access.get_schedule_by_date(next_date.isoformat())
        shops_per_day = int(data_access.get_setting("shops_per_day", "20"))
        
        if existing and len(existing) >= shops_per_day:
            next_date += timedelta(days=1)
            attempts += 1
            continue
        
        return next_date
    
    return current + timedelta(days=7)


def _perform_reschedule(shop_id: str, original_date: str, new_date: str):
    """Perform rescheduling."""
    try:
        data_access.update_schedule_status(original_date, shop_id, "Rescheduled", None)
        
        with data_access.get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT shop_id, shop_name, address, region, district, 
                       brand, lat, lng, is_mtr
                FROM shop_master
                WHERE shop_id = ?
            """, (shop_id,))
            shop_row = cur.fetchone()
        
        if not shop_row:
            st.error(f"❌ Shop not found: {shop_id}")
            return
        
        existing_schedule = data_access.get_schedule_by_date(new_date)
        next_group = 1
        if existing_schedule:
            max_group = max([s.get('group_number', 0) for s in existing_schedule])
            next_group = max_group + 1
        
        with data_access.get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO schedule (
                    shop_id, shop_name, address, region, district,
                    brand, lat, lng, is_mtr, schedule_date, group_number, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'Planned')
            """, (
                shop_row[0], shop_row[1], shop_row[2], shop_row[3], shop_row[4],
                shop_row[5], shop_row[6], shop_row[7], shop_row[8], new_date, next_group
            ))
        
        st.success(f"✅ Rescheduled {shop_id} to {new_date}")
        _sync_to_sharepoint(shop_id, "Rescheduled")
        
        if 'show_manual_date' in st.session_state:
            del st.session_state['show_manual_date']
        
        st.rerun()
    except Exception as e:
        st.error(f"❌ Reschedule failed: {str(e)}")


def _sync_to_sharepoint(shop_id: str, new_status: str):
    """Sync status to SharePoint."""
    list_url = data_access.get_setting("SHAREPOINT_LIST_URL")
    token = data_access.get_setting("SHAREPOINT_ACCESS_TOKEN")
    
    if not list_url or not token:
        return
    
    try:
        item_id = data_access._get_sharepoint_item_id(shop_id, list_url, token)
        if item_id:
            data_access.update_sharepoint_item_status(item_id, new_status, list_url, token)
    except:
        pass
