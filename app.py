import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder

# URL of the Excel file in your GitHub repo (raw file link)
EXCEL_URL = "https://raw.githubusercontent.com/guscolby/arcsearch/main/ARC%20RAIDERS%20MATS.xlsx"

st.set_page_config(page_title="ARC Raiders Material Search", layout="wide")
st.title("🔍 ARC Raiders Material Search")
st.caption("Interactive search powered by live data from the ARC RAIDERS MATS spreadsheet")

@st.cache_data
def load_data():
    xls = pd.ExcelFile(EXCEL_URL)

    craftables = pd.read_excel(xls, "01_Craftable")
    components = pd.read_excel(xls, "03_Component")
    comp_usage = pd.read_excel(xls, "04_ComponentUsage")
    comp_loc = pd.read_excel(xls, "05_ComponentLocation")
    dismantle = pd.read_excel(xls, "06_DismantleResults")
    locations = pd.read_excel(xls, "02_Location")

    # Merge ComponentLocation with Location to get readable names
    comp_loc = comp_loc.merge(locations, on="LocationID", how="left")

    # Build lookup tables
    found_in = (
        comp_loc.groupby("ComponentID")["LocationName"]
        .apply(lambda x: ", ".join(sorted(set(x.dropna()))))
        .rename("Found In")
    )

    used_in = (
        comp_usage.merge(craftables, on="CraftableID", how="left")
        .groupby("ComponentID")["CraftableName"]
        .apply(lambda x: ", ".join(sorted(set(x.dropna()))))
        .rename("Used In")
    )

    dismantle_to = (
        dismantle.merge(components, left_on="ResultComponentID", right_on="ComponentID", suffixes=("", "_Result"))
        .groupby("SourceComponentID")["ComponentName_Result"]
        .apply(lambda x: ", ".join(sorted(set(x.dropna()))))
        .rename("Dismantles To")
    )

    # Merge everything into the main components table
    df = (
        components.set_index("ComponentID")
        .join(found_in)
        .join(used_in)
        .join(dismantle_to)
        .reset_index()
    )

    # Handle missing data gracefully
    df["Found In"].fillna("Unknown", inplace=True)
    df["Used In"].fillna("No known use", inplace=True)
    df["Dismantles To"].fillna("Cannot be dismantled", inplace=True)

    return df

df = load_data()

# Sidebar filters
st.sidebar.header("Filters")
rarities = ["All"] + sorted(df["ComponentRarity"].dropna().unique())
selected_rarity = st.sidebar.selectbox("Filter by rarity:", rarities)

show_unknown = st.sidebar.checkbox("Show items with unknown location", value=True)

# Apply filters
filtered_df = df.copy()
if selected_rarity != "All":
    filtered_df = filtered_df[filtered_df["ComponentRarity"] == selected_rarity]

if not show_unknown:
    filtered_df = filtered_df[filtered_df["Found In"] != "Unknown"]

# Rarity color coding (HTML)
rarity_colors = {
    "Common": "#b0b0b0",
    "Green": "#00c000",
    "Blue": "#0080ff",
    "Purple": "#a000ff",
    "Orange": "#ff8000",
    "Legendary": "#ffcc00"
}

def rarity_html(rarity):
    color = rarity_colors.get(rarity, "#ffffff")
    return f'<span style="color:{color}; font-weight:bold;">{rarity}</span>'

filtered_df["Rarity"] = filtered_df["ComponentRarity"].apply(rarity_html)

# Build grid
gb = GridOptionsBuilder.from_dataframe(filtered_df[[
    "ComponentName", "Rarity", "ComponentSellPrice", "Used In", "Found In", "Dismantles To"
]])
gb.configure_default_column(wrapText=True, autoHeight=True)
gb.configure_grid_options(domLayout='autoHeight')
grid_options = gb.build()

# Display grid
st.markdown("### Results")
AgGrid(
    filtered_df[[
        "ComponentName", "Rarity", "ComponentSellPrice", "Used In", "Found In", "Dismantles To"
    ]],
    gridOptions=grid_options,
    enable_enterprise_modules=False,
    allow_unsafe_jscode=True,
    height=600,
)

st.caption("Update the spreadsheet in the GitHub repo to automatically refresh app data on next reload.")
