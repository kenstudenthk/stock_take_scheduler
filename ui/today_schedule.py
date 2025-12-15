# ui/today_schedule.py

import streamlit as st
import pandas as pd
from datetime import date, timedelta
from core import data_access, holidays

def render():
    """Render the Today Schedule page."""
    st.subheader("📅 Today's Schedule")
    
    # Date selector
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
    
    # Group by group_number
    groups = df.groupby("group_number")
    
    st.markdown(f"### 📊 Total: {len(df)} shops in {len(groups)} groups")
    
    # Display each group
    for group_num, group_df in groups:
        with st.expander(f"🏪 Group {group_num} ({len(group_df)} shops)", expanded=True):
            
            for idx, row in group_df.iterrows():
                col1, col2, col3 = st.columns([3, 1, 1])
                
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
                        # ✅ Done button
                        if st.button("✅ Done", key=f"done_{row['shop_id']}_{selected_date}"):
                            _mark_as_done(row['shop_id'], selected_date.isoformat())
                        
                        # 🚫 Closed button - with confirmation
                        if st.button("🚫 Closed", key=f"closed_{row['shop_id']}_{selected_date}"):
                            _show_closed_confirmation(row['shop_id'], row['shop_name'], selected_date.isoformat())
                        
                        # 📅 Reschedule button - with smart suggestion
                        if st.button("📅 Reschedule", key=f"reschedule_{row['shop_id']}_{selected_date}"):
                            _show_reschedule_dialog(row['shop_id'], row['shop_name'], selected_date.isoformat())


def _mark_as_done(shop_id: str, schedule_date: str):
    """Mark a shop as Done."""
    try:
        # Update local database
        data_access.update_schedule_status(shop_id, schedule_date, "Done")
        st.success(f"✅ Marked {shop_id} as Done.")
        
        # Sync to SharePoint
        _sync_to_sharepoint(shop_id, "Done")
        
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Failed to mark as Done: {str(e)}")


def _show_closed_confirmation(shop_id: str, shop_name: str, schedule_date: str):
    """
    Show confirmation dialog for marking shop as Closed.
    Uses st.dialog to create a modal confirmation.
    """
    @st.dialog(f"🚫 確認店舖關閉", width="large")
    def confirm_closed():
        st.warning("⚠️ **警告：此操作將標記店舖為永久關閉**")
        
        st.markdown(f"""
        **店舖資訊：**
        - 店舖代碼：`{shop_id}`
        - 店舖名稱：{shop_name}
        - 排程日期：{schedule_date}
        
        ---
        
        **確認此店舖已永久關閉？**
        - 此店舖將從未來的排程中移除
        - 狀態將同步到 SharePoint List
        """)
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("✅ 是，確認關閉", type="primary", use_container_width=True):
                try:
                    # Update local database
                    data_access.update_schedule_status(shop_id, schedule_date, "Closed")
                    
                    # Mark shop as inactive
                    with data_access.get_db_connection() as conn:
                        cur = conn.cursor()
                        cur.execute(
                            "UPDATE shop_master SET is_active = 'N' WHERE shop_id = ?",
                            (shop_id,)
                        )
                    
                    st.success(f"✅ 已標記 {shop_id} 為關閉")
                    
                    # Sync to SharePoint
                    _sync_to_sharepoint(shop_id, "Closed")
                    
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"❌ 操作失敗: {str(e)}")
        
        with col2:
            if st.button("❌ 否，取消", use_container_width=True):
                st.rerun()
    
    # Show the dialog
    confirm_closed()


def _show_reschedule_dialog(shop_id: str, shop_name: str, original_date: str):
    """
    Show reschedule dialog with smart date suggestion.
    """
    @st.dialog(f"📅 重新排程：{shop_name}", width="large")
    def reschedule_dialog():
        st.markdown(f"""
        **店舖資訊：**
        - 店舖代碼：`{shop_id}`
        - 店舖名稱：{shop_name}
        - 原定日期：{original_date}
        """)
        
        st.markdown("---")
        
        # Calculate next available date
        suggested_date = _get_next_available_date(original_date)
        
        st.info(f"💡 **建議的重新排程日期：{suggested_date.strftime('%Y年%m月%d日 (%A)')}**")
        
        st.markdown("**請選擇：**")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button(
                f"✅ 接受建議日期\n{suggested_date.strftime('%Y-%m-%d')}",
                type="primary",
                use_container_width=True
            ):
                _perform_reschedule(shop_id, original_date, suggested_date.isoformat())
        
        with col2:
            if st.button("📆 手動選擇日期", use_container_width=True):
                st.session_state['show_manual_date'] = True
                st.rerun()
        
        # Manual date selection
        if st.session_state.get('show_manual_date', False):
            st.markdown("---")
            st.markdown("### 📆 手動選擇重新排程日期")
            
            manual_date = st.date_input(
                "選擇新日期",
                value=suggested_date,
                min_value=date.today(),
                key="manual_reschedule_date"
            )
            
            # Check if selected date is a holiday
            if holidays.is_holiday(manual_date.isoformat()):
                st.warning(f"⚠️ {manual_date.strftime('%Y-%m-%d')} 是公眾假期")
            
            col_confirm, col_cancel = st.columns(2)
            
            with col_confirm:
                if st.button("✅ 確認重新排程", type="primary", use_container_width=True):
                    _perform_reschedule(shop_id, original_date, manual_date.isoformat())
            
            with col_cancel:
                if st.button("❌ 取消", use_container_width=True):
                    st.session_state['show_manual_date'] = False
                    st.rerun()
    
    # Show the dialog
    reschedule_dialog()


def _get_next_available_date(original_date: str) -> date:
    """
    Calculate the next available date for rescheduling.
    Skips holidays and weekends.
    
    Args:
        original_date: Original schedule date (ISO format)
        
    Returns:
        Next available date
    """
    from datetime import datetime
    
    current = datetime.fromisoformat(original_date).date()
    
    # Start from the day after original date
    next_date = current + timedelta(days=1)
    
    # Find next available working day
    max_attempts = 30  # Look ahead max 30 days
    attempts = 0
    
    while attempts < max_attempts:
        # Check if it's a weekend
        if next_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
            next_date += timedelta(days=1)
            attempts += 1
            continue
        
        # Check if it's a holiday
        if holidays.is_holiday(next_date.isoformat()):
            next_date += timedelta(days=1)
            attempts += 1
            continue
        
        # Check if the date already has schedule (optional: avoid overload)
        existing = data_access.get_schedule_by_date(next_date.isoformat())
        shops_per_day = int(data_access.get_setting("shops_per_day", "20"))
        
        if existing and len(existing) >= shops_per_day:
            # This day is full, try next day
            next_date += timedelta(days=1)
            attempts += 1
            continue
        
        # Found a suitable date
        return next_date
    
    # If no suitable date found within 30 days, return 7 days from original
    return current + timedelta(days=7)


def _perform_reschedule(shop_id: str, original_date: str, new_date: str):
    """
    Perform the actual rescheduling operation.
    """
    try:
        # Update status of original schedule
        data_access.update_schedule_status(shop_id, original_date, "Rescheduled")
        
        # Get shop details
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
            st.error(f"❌ 找不到店舖資料: {shop_id}")
            return
        
        # Get next available group number for new date
        existing_schedule = data_access.get_schedule_by_date(new_date)
        next_group = 1
        if existing_schedule:
            max_group = max([s.get('group_number', 0) for s in existing_schedule])
            next_group = max_group + 1
        
        # Insert new schedule
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
        
        st.success(f"✅ 已重新排程 {shop_id} 到 {new_date}")
        
        # Sync to SharePoint
        _sync_to_sharepoint(shop_id, "Rescheduled")
        
        # Clear manual date flag
        if 'show_manual_date' in st.session_state:
            del st.session_state['show_manual_date']
        
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ 重新排程失敗: {str(e)}")
        import traceback
        st.code(traceback.format_exc())


def _sync_to_sharepoint(shop_id: str, new_status: str):
    """
    Sync status update to SharePoint List using Microsoft Graph API.
    """
    list_url = data_access.get_setting("SHAREPOINT_LIST_URL")
    token = data_access.get_setting("SHAREPOINT_ACCESS_TOKEN")
    status_field = data_access.get_setting("SHAREPOINT_STATUS_FIELD", "ScheduleStatus")
    
    if not list_url or not token:
        st.info("ℹ️ SharePoint sync skipped: Settings not configured.")
        return
    
    try:
        # Step 1: Get Item ID
        with st.spinner(f"🔍 Looking up SharePoint Item for {shop_id}..."):
            item_id = data_access._get_sharepoint_item_id(shop_id, list_url, token)
        
        if item_id is None:
            st.warning(f"⚠️ Could not find SharePoint Item for shop: {shop_id}")
            return
        
        # Step 2: Update status
        with st.spinner(f"📤 Syncing to SharePoint (Item {item_id})..."):
            success = data_access.update_sharepoint_item_status(
                item_id=item_id,
                new_status=new_status,
                list_url=list_url,
                token=token,
                status_field_internal_name=status_field
            )
        
        if success:
            st.success(f"✅ SharePoint synced: {shop_id} → {new_status}")
        else:
            st.error(f"❌ SharePoint sync failed for {shop_id}")
            
    except Exception as e:
        st.error(f"❌ SharePoint sync error: {str(e)}")
