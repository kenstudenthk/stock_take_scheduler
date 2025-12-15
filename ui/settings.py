# ui/settings.py

import streamlit as st

from core import data_access, holidays, amap_client


def render():
    st.subheader("Settings")

    # --- Capacity settings ---
    st.markdown("### Scheduling capacity")
           
    cap_str = data_access.get_setting("shops_per_day", "20")
    try:
        current_cap = int(cap_str)
    except (TypeError, ValueError):
        current_cap = 20

    new_cap = st.number_input(
        "Maximum shops per day (used for Generate Schedule and re-schedule capacity)",
        min_value=1,
        max_value=60,
        value=current_cap,
        step=1,
    )

    if st.button("Save capacity"):
        data_access.set_setting("shops_per_day", str(new_cap))
        st.success(f"Saved: max {new_cap} shops per day.")
    st.caption(
        "This value is used when generating new schedules and when re-scheduling "
        "shops (capacity-aware)."
    )

    st.markdown("---")

    # --- Group settings ---
    st.markdown("### Daily group configuration")

    raw_groups = data_access.get_setting("groups_per_day", None)
    raw_per_group = data_access.get_setting("shops_per_group", None)

    try:
        groups_per_day = int(raw_groups) if raw_groups is not None else 3
    except (TypeError, ValueError):
        groups_per_day = 3

    try:
        shops_per_group = int(raw_per_group) if raw_per_group is not None else 3
    except (TypeError, ValueError):
        shops_per_group = 3

    col1, col2 = st.columns(2)

    with col1:
        groups_per_day_new = st.number_input(
            "Groups per day",
            min_value=1,
            max_value=10,
            value=groups_per_day,
            step=1,
            help="Number of parallel groups (e.g. 3 teams).",
        )

    with col2:
        shops_per_group_new = st.number_input(
            "Shops per group",
            min_value=1,
            max_value=10,
            value=shops_per_group,
            step=1,
            help="Target shops per group (e.g. 3 shops per team).",
        )

    if st.button("Save group settings"):
        data_access.set_setting("groups_per_day", str(groups_per_day_new))
        data_access.set_setting("shops_per_group", str(shops_per_group_new))

        # Keep shops_per_day consistent
        total_per_day = groups_per_day_new * shops_per_group_new
        data_access.set_setting("shops_per_day", str(total_per_day))

        st.success(
            f"Saved: {groups_per_day_new} groups/day × "
            f"{shops_per_group_new} shops/group = {total_per_day} shops/day."
        )

    st.caption(
        "Schedules will be split into groups (Group 1, Group 2, ...) per day. "
        "Remaining shops (if not divisible) will fill Group 1, then Group 2, etc."
    )

    st.markdown("---")

    # --- Amap API configuration ---
    st.markdown("### AMap API configuration")

    api_key = data_access.get_setting("AMAP_WEB_KEY", "")

    new_key = st.text_input(
        "AMap Web Service API Key",
        value=api_key or "",
        type="password",
        help="Used for distance and routing calculations. Get your key from https://lbs.amap.com/",
    )

    col1, col2 = st.columns([1, 1])

    with col1:
        if st.button("Save AMap API key"):
            data_access.set_setting("AMAP_WEB_KEY", new_key.strip())
            st.success("AMap API key saved.")
            st.rerun()

    with col2:
        if st.button("Test API key"):
            if not new_key.strip():
                st.error("Please enter an API key first.")
            else:
                with st.spinner("Testing API connection..."):
                    try:
                        data_access.set_setting("AMAP_WEB_KEY", new_key.strip())
                        is_valid = amap_client.test_api_key()
                        if is_valid:
                            st.success("✓ API key is valid and working!")
                        else:
                            st.error("✗ API key test failed. Please check your key.")
                    except Exception as e:
                        st.error(f"✗ Error testing API: {str(e)}")

    if api_key:
        st.caption("✓ API key is configured")
    else:
        st.warning("⚠️ No API key configured. Distance calculations will not work.")

    st.markdown("---")

    # --- Holiday management ---
    st.markdown("### Holiday management")

    with st.expander("View/Edit holidays"):
        holiday_df = holidays.get_holiday_df()
        if not holiday_df.empty:
            st.dataframe(holiday_df, use_container_width=True)
            st.caption(f"Total holidays: {len(holiday_df)}")
        else:
            st.info("No holidays configured.")

        st.markdown("##### Add new holiday")
        col1, col2, col3 = st.columns([2, 2, 1])

        with col1:
            new_holiday_date = st.date_input("Date", key="new_holiday_date")

        with col2:
            new_holiday_name = st.text_input(
                "Holiday name (Chinese)", key="new_holiday_name"
            )

        with col3:
            new_holiday_type = st.selectbox(
                "Type",
                ["Statutory", "General"],
                key="new_holiday_type",
            )

        if st.button("Add holiday"):
            if new_holiday_name.strip():
                holidays.add_holiday(
                    date=new_holiday_date.isoformat(),
                    name_zh=new_holiday_name.strip(),
                    holiday_type=new_holiday_type,
                )
                st.success(f"Added holiday: {new_holiday_name}")
                st.rerun()
            else:
                st.error("Please enter a holiday name.")

        if holiday_df.empty:
            if st.button("Load default Hong Kong holidays (2025-2026)"):
                holidays.init_default_holidays()
                st.success("Default holidays loaded!")
                st.rerun()

    st.markdown("---")

    # --- SharePoint / Power Automate Sync (SharePoint List) ---
    st.markdown("### ☁️ SharePoint / Power Automate Sync")

    pa_url = st.text_input(
        "Power Automate HTTP URL",
        value=data_access.get_setting("PA_LIST_URL", ""),
        type="password",
        help="貼上 Power Automate Flow（Get items 的 HTTP 觸發器）產生的 URL。",
        key="pa_list_url",
    )

    col_pa1, col_pa2 = st.columns(2)

    with col_pa1:
        if st.button("💾 Save Power Automate URL"):
            data_access.set_setting("PA_LIST_URL", (pa_url or "").strip())
            st.success("Power Automate URL 已儲存。")

    with col_pa2:
        if st.button("📥 Sync shops from SharePoint List"):
            url = data_access.get_setting("PA_LIST_URL")
            if not url:
                st.error("請先在左邊儲存 Power Automate URL。")
            else:
                import requests
                try:
                    with st.spinner("從 SharePoint 下載資料中..."):
                        resp = requests.get(url, headers={"Accept": "application/json"})
                        resp.raise_for_status()

                        content_type = resp.headers.get("Content-Type", "")

                        if "json" in content_type:
                            data = resp.json()
                            if isinstance(data, list):
                                items = data
                            elif isinstance(data, dict):
                                items = data.get("value", data)
                            else:
                                raise ValueError("未知的 JSON 格式")

                            with st.spinner(f"更新資料庫 ({len(items)} 筆 JSON)..."):
                                data_access.import_shops_from_json(items, overwrite=True)
                        else:
                            csv_path = "data/MxStockTakeMasterList.csv"
                            with open(csv_path, "wb") as f:
                                f.write(resp.content)

                            st.success("✓ CSV 檔案已下載。正在匯入資料庫...")
                            with st.spinner("更新資料庫 (CSV)..."):
                                data_access.import_shops_from_csv(overwrite=True)

                    st.success("✅ 已完成與 SharePoint 同步店舖資料。")
                    st.balloons()
                except Exception as e:
                    st.error(f"同步失敗：{e}")
                    
    st.markdown("---")
    st.markdown("### SharePoint settings")

    sp_url = data_access.get_setting("SHAREPOINT_LIST_URL", "") or ""
    sp_token = data_access.get_setting("SHAREPOINT_ACCESS_TOKEN", "") or ""

    sp_url_new = st.text_input(
        "SharePoint List API URL",
        value=sp_url,
        help="例如: https://xxx.sharepoint.com/sites/YourSite/_api/web/lists/getbytitle('MxStockTakeMasterList')"
    )

    sp_token_new = st.text_input(
        "SharePoint access token (Bearer)",
        value=sp_token,
        type="password",
        help="暫時可貼從 Postman / Graph Explorer 拿到的 Bearer token 來測試"
    )

    if st.button("Save SharePoint settings"):
        data_access.set_setting("SHAREPOINT_LIST_URL", sp_url_new.strip())
        data_access.set_setting("SHAREPOINT_ACCESS_TOKEN", sp_token_new.strip())
        st.success("SharePoint settings saved.")
    
    st.markdown("---")
    st.markdown("### Power Automate (write schedule)")

    pa_write_url = st.text_input(
        "Power Automate URL for writing schedule",
        value=data_access.get_setting("PA_SCHEDULE_WRITE_URL", ""),
        type="password",
        help="貼上用來接收 schedule 的 HTTP Flow URL。",
        key="pa_schedule_write_url",
    )

    if st.button("💾 Save schedule write URL", key="save_pa_schedule_write_url"):
        data_access.set_setting("PA_SCHEDULE_WRITE_URL", (pa_write_url or "").strip())
        st.success("Schedule write URL 已儲存。")

def import_shops_from_sharepoint(list_url, token, overwrite=False):
    """
    Import shops from SharePoint using Microsoft Graph API
    """
    import requests
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    
    # 加上 expand=fields 來取得欄位資料
    url = f"{list_url}?expand=fields"
    
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    
    data = response.json()
    items = data.get("value", [])
    
    # 處理每個 item
    for item in items:
        fields = item.get("fields", {})
        
        # 對應欄位名稱
        shop_id = fields.get("ShopID") or fields.get("shop_id")
        shop_name = fields.get("Title") or fields.get("ShopName")
        region = fields.get("Region")
        # ... 其他欄位

    # 從 settings 讀取（如果未提供）
    if list_url is None:
        list_url = get_setting("SHAREPOINT_LIST_URL")
    if token is None:
        token = get_setting("SHAREPOINT_ACCESS_TOKEN")
    
    if not list_url or not token:
        raise ValueError("SharePoint URL 或 Token 未設定")
    
    print("📥 開始從 SharePoint 匯入店舖資料...")
    
    # Step 1: 取得所有 SharePoint List 項目
    query_url = f"{list_url}/items?$select=id&$expand=fields&$top=5000"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json"
    }
    
    try:
        response = requests.get(query_url, headers=headers, timeout=30)
        
        if response.status_code != 200:
            raise Exception(f"SharePoint API 錯誤: {response.status_code} - {response.text}")
        
        data = response.json()
        items = data.get("value", [])
        
        print(f"📊 從 SharePoint 取得 {len(items)} 筆資料")
        
        if not items:
            return {"success": 0, "failed": 0, "skipped": 0}
        
        # Step 2: 解析資料並寫入資料庫
        success_count = 0
        failed_count = 0
        skipped_count = 0
        
        with get_db_connection() as conn:
            cur = conn.cursor()
            
            for item in items:
                try:
                    fields = item.get("fields", {})
                    
                    # 必要欄位檢查
                    shop_id = fields.get("field_6")  # Shop Code
                    if not shop_id:
                        print(f"⚠️ 跳過：缺少 Shop Code (field_6)")
                        skipped_count += 1
                        continue
                    
                    # 如果不覆蓋，檢查是否已存在
                    if not overwrite:
                        cur.execute("SELECT 1 FROM shop_master WHERE shop_id = ?", (shop_id,))
                        if cur.fetchone():
                            print(f"⏭️ 跳過 {shop_id}（已存在）")
                            skipped_count += 1
                            continue
                    
                    # 準備資料（對應您的 SharePoint 欄位）
                    shop_data = {
                        "shop_id": shop_id,
                        "shop_name": fields.get("field_7", ""),  # Shop Name
                        "address": fields.get("field_8", ""),  # Address
                        "region": fields.get("field_9", ""),  # Region
                        "district": fields.get("field_10", ""),  # District
                        "brand": fields.get("field_11", ""),  # Brand
                        "brand_code": fields.get("field_12", ""),  # Brand Code
                        "division": fields.get("field_13", ""),  # Division
                        "english_address": fields.get("field_14", ""),  # English Address
                        "location": fields.get("field_15", ""),  # Location
                        "lat": fields.get("field_20", 0.0),  # Latitude
                        "lng": fields.get("field_21", 0.0),  # Longitude
                        "brand_icon_url": fields.get("field_22", ""),  # Brand Icon
                        "is_mtr": fields.get("field_17", "N"),  # Is MTR
                        "phone": fields.get("field_37", ""),  # Phone
                        "is_active": "Y" if fields.get("field_35") == "Y" else "N",  # Active flag
                    }
                    
                    # 寫入或更新資料庫
                    if overwrite:
                        # UPSERT 操作
                        cur.execute("""
                            INSERT OR REPLACE INTO shop_master (
                                shop_id, shop_name, address, region, district,
                                brand, brand_code, division, english_address, location,
                                lat, lng, brand_icon_url, is_mtr, phone, is_active
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            shop_data["shop_id"],
                            shop_data["shop_name"],
                            shop_data["address"],
                            shop_data["region"],
                            shop_data["district"],
                            shop_data["brand"],
                            shop_data["brand_code"],
                            shop_data["division"],
                            shop_data["english_address"],
                            shop_data["location"],
                            shop_data["lat"],
                            shop_data["lng"],
                            shop_data["brand_icon_url"],
                            shop_data["is_mtr"],
                            shop_data["phone"],
                            shop_data["is_active"]
                        ))
                    else:
                        # 只插入新記錄
                        cur.execute("""
                            INSERT INTO shop_master (
                                shop_id, shop_name, address, region, district,
                                brand, brand_code, division, english_address, location,
                                lat, lng, brand_icon_url, is_mtr, phone, is_active
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            shop_data["shop_id"],
                            shop_data["shop_name"],
                            shop_data["address"],
                            shop_data["region"],
                            shop_data["district"],
                            shop_data["brand"],
                            shop_data["brand_code"],
                            shop_data["division"],
                            shop_data["english_address"],
                            shop_data["location"],
                            shop_data["lat"],
                            shop_data["lng"],
                            shop_data["brand_icon_url"],
                            shop_data["is_mtr"],
                            shop_data["phone"],
                            shop_data["is_active"]
                        ))
                    
                    success_count += 1
                    print(f"✅ 成功匯入: {shop_id}")
                    
                except Exception as e:
                    failed_count += 1
                    print(f"❌ 匯入失敗 {shop_id}: {e}")
            
            conn.commit()
        
        print(f"\n📊 匯入完成：")
        print(f"   ✅ 成功: {success_count}")
        print(f"   ❌ 失敗: {failed_count}")
        print(f"   ⏭️ 跳過: {skipped_count}")
        
        return {
            "success": success_count,
            "failed": failed_count,
            "skipped": skipped_count
        }
        
    except Exception as e:
        print(f"❌ SharePoint 匯入失敗: {e}")
        import traceback
        traceback.print_exc()
        raise




