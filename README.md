# Stock Take Scheduler
 
A Streamlit-based application for managing and scheduling shop stock-taking operations across Hong Kong and Macau.
 
## Features
 
- 📅 **Today Schedule**: View daily shop visit schedules with interactive maps

- 🗓️ **Generate Schedule**: Auto-generate optimized schedules with route planning

- 🗺️ **All Shops**: Search, filter, and export shop data with map visualization

- 🔍 **View Schedule**: Advanced search and filtering of schedule records

- ⚙️ **Settings**: Configure capacity, holidays, and API keys
 
## Tech Stack
 
- **Framework**: Streamlit

- **Database**: SQLite

- **Maps**: Pydeck (deck.gl)

- **Routing**: AMap API (高德地图)

- **Data**: Pandas

## Installation
 
1. Clone the repository:
git clone https://github.com/<your-username>/stock-take-scheduler.git
cd stock-take-scheduler

1. **Create virtual environment (optional but recommended)**
python -m venv .venv
source .venv/bin/activate # Windows: .venv\Scripts\activate


1. **Install dependencies**
pip install -r requirements.txt


1. **Run the app**
streamlit run app.py
## Configuration
### AMap API Key
1. Get a Web Service API key from AMap (高德地图) developer console.  
2. Run the app and go to the **Settings** tab.  
1. Paste the key into **"AMap Web Service API Key"** and click **Save AMap API key**.  4. Use **Test API key** to verify connectivity.
### Shop Master CSV Import
1. Place your latest `MxStockTakeMasterList.csv` into the `data/` folder.  
1. In the **Settings** tab, click **"Re-import Shops from CSV"**.
2. The app will rebuild `shop_master` from the CSV and update regions/brands/etc.
   
> Note: By default, only shops with `Available = "Y"` in the CSV are marked as active (`is_active = 1`).
## Usage Tips
### All Shops Tab
- Use **Region** multi-select to choose HK / KN / NT / Islands / MO combinations.  
- Use **District** multi-select (dynamic from DB) to pick specific districts.  - Use **Brand** filter (partial match) to focus on specific brands.  
- Use **Status** multi-select to focus on Planned / Done / Closed / Rescheduled.  
- Use **Export** section to:  
  - Download filtered results as CSV (UTF-8, Chinese supported).  
  - Open filtered shops in **Google Maps** (markers or route).  
  - Open filtered shops in **AMap** (markers or route).

### Generate Schedule Tab
- Choose **Daily shops to schedule** and **Start date**. 
- Select regions and (optionally) specific districts.  
- Configure **MTR inclusion** and **cross-region** behavior.
- Optionally enable AMap distance/time calculation.  
- Click **Generate schedule** and review statistics and summary.
- 
## Deployment (Streamlit Cloud)
  1. Push this repo to GitHub.  
  2. In Streamlit Community Cloud, create a new app pointing to `app.py`.  3. Ensure `requirements.txt` is present in the repo.  
  3.  Upload or mount your `data` files as needed (for public deployments, use sanitized sample data).
   
## License
This project is licensed under the MIT License – see the [LICENSE](LI-CENSE) file for details.

## Author
- Kilson  
- Contact: Kilson.Km.li@PCCW.com
 