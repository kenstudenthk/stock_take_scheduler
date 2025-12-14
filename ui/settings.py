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




