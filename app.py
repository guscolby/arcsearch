import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

# ---------------------------------------------------------
# APP CONFIG
# ---------------------------------------------------------
st.set_page_config(page_title="ARC Raiders Materials Search", layout="wide")

st.title("🔍 ARC Raiders Materials Search (PowerDashboard)")
st.caption("Interactive database of item rarities, uses, and dismantle data.")

# ---------------------------------------------------------
# LOAD DATA
# ---------------------------------------------------------
@st.cache_data
def load_data():
    # Direct GitHub download link (raw file)
    url = "https://raw.githubusercontent.com/guscolby/arcsearch/main/ARC%20RAIDERS%20MATS.xlsx"
    xls = pd.ExcelFile(url)

    # Load relevant sheets
    items = pd.read_excel(xls, "Items")
    comps = pd.read_excel(xls, "Components")
    dismantle = pd.read_excel(xls, "Dismantle")
    comp_loc = pd.read_excel(xls, "ComponentLocation")
    locs = pd.read_excel(xls, "Locations")

    # Merge location names into ComponentLocation
    comp_loc = comp_loc.merge(locs[["LocationID", "LocationName"]], on="LocationID", how="left")

    # Group the "found in" data
    found_in = (
        comp_loc.groupby("ComponentID")["LocationName"]
        .apply(lambda x: ", ".join(sorted(set(x.dropna()))))
        .rename("Location")
        .reset_index()
    )

    # Merge datasets
    merged = (
        comps.merge(items, on="ItemID", how="left")
        .merge(dismantle, on="ComponentID", how="left")
        .merge(found_in, on="ComponentID", how="left")
    )

    # Clean and fill missing values
    merged["Item Name"] = merged["ItemName"].fillna("Unnamed Item")
    merged["Rarity"] = merged["Rarity"].fillna("Unknown")
    merged["Sell Price"] = merged["SellPrice"].fillna(0)
    merged["Location"] = merged["Location"].fillna("Unknown")

    merged["Recycles To"] = merged["RecyclesTo"].fillna("Cannot be dismantled")

    merged = merged[
        ["Item Name", "Rarity", "Sell Price", "Recycles To", "Location"]
    ]

    return merged


merged_df = load_data()

# ---------------------------------------------------------
# SIDEBAR FILTERS
# ---------------------------------------------------------
with st.sidebar:
    st.header("Search Filters")
    search_query = st.text_input("Search item name:", "")
    show_unknown = st.checkbox("Show items with unknown location", value=True)

# ---------------------------------------------------------
# APPLY FILTERS
# ---------------------------------------------------------
filtered = merged_df.copy()

if search_query:
    filtered = filtered[filtered["Item Name"].str.contains(search_query, case=False, na=False)]

if not show_unknown:
    filtered = filtered[filtered["Location"] != "Unknown"]

results = filtered.copy()

# ---------------------------------------------------------
# RARITY COLOR STYLING
# ---------------------------------------------------------
rarity_colors = {
    "Common": "white",
    "Green": "#4CAF50",
    "Blue": "#2196F3",
    "Purple": "#9C27B0",
    "Gold": "#FFC107",
    "Legendary": "#FF5722",
    "Unknown": "#9E9E9E",
}

def rarity_color(val):
    color = rarity_colors.get(val, "white")
    return f"color: {color}; font-weight: bold;"

# ---------------------------------------------------------
# DISPLAY RESULTS
# ---------------------------------------------------------
if results is not None and not results.empty:
    st.markdown(f"### Search Results ({len(results)} items found)")
    styled_df = results.style.applymap(rarity_color, subset=["Rarity"])

    gb = GridOptionsBuilder.from_dataframe(results)
    gb.configure_pagination(enabled=True)
    gb.configure_default_column(
        groupable=False,
        value=True,
        enableRowGroup=False,
        enablePivot=False,
        enableValue=True,
    )
    gb.configure_selection('single')
    grid_options = gb.build()

    AgGrid(
        results,
        gridOptions=grid_options,
        height=500,
        theme="streamlit",
        update_mode=GridUpdateMode.SELECTION_CHANGED,
    )

else:
    st.warning("No matching items found. Try adjusting your search or filters.")
