# app.py
import io
import pandas as pd
import streamlit as st
from urllib.request import urlopen
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

st.set_page_config(layout="wide", page_title="Arc Raiders - Component Browser")

# ---------- CONFIG ----------
GITHUB_XLSX_URL = "https://raw.githubusercontent.com/guscolby/arcsearch/main/ARC%20RAIDERS%20MATS.xlsx"
# ----------------------------

@st.cache_data(ttl=300)
def load_workbook(url: str):
    """Fetches Excel workbook from GitHub (raw link)."""
    data = urlopen(url).read()
    xlsx = pd.read_excel(io.BytesIO(data), sheet_name=None, engine="openpyxl")
    return xlsx

# --- Color helper ---
RARITY_COLORS = {
    "Common": "#CCCCCC",
    "Uncommon": "#4CAF50",   # Green
    "Rare": "#2196F3",       # Blue
    "Epic": "#9C27B0",       # Purple
    "Legendary": "#FF9800",  # Orange
    "Green": "#4CAF50",
    "Blue": "#2196F3",
    "Purple": "#9C27B0",
    "Orange": "#FF9800",
    "Gray": "#9E9E9E",
}

# --- Utility for applying rarity color ---
def colorize_rarity(val):
    if pd.isna(val):
        return ""
    color = RARITY_COLORS.get(val, "#FFFFFF")
    return f'background-color: {color}; color: white; text-align: center; font-weight: bold;'

# --- Load workbook ---
with st.spinner("Loading workbook from GitHub..."):
    xlsx = load_workbook(GITHUB_XLSX_URL)

# Get necessary sheets
craft = xlsx.get("01_Craftable", pd.DataFrame())
loc = xlsx.get("02_Location", pd.DataFrame())
comp = xlsx.get("03_Component", pd.DataFrame())
usage = xlsx.get("04_ComponentUsage", pd.DataFrame())
comp_loc = xlsx.get("05_ComponentLocation", pd.DataFrame())
dis = xlsx.get("06_DismantleResults", pd.DataFrame())

# Normalize column names
for df in [craft, loc, comp, usage, comp_loc, dis]:
    df.columns = [str(c).strip() for c in df.columns]

# --- Map columns (simplified) ---
comp = comp.rename(columns={
    "ComponentID": "ComponentID",
    "ComponentName": "Name",
    "ComponentRarity": "Rarity",
    "ComponentSellPrice": "Sell Price"
})

# --- Build lookups ---
craft_map = pd.Series(craft["CraftableName"].values, index=craft["CraftableID"]).to_dict()
loc_map = pd.Series(loc["LocationName"].values, index=loc["LocationID"]).to_dict()
comp_map = pd.Series(comp["Name"].values, index=comp["ComponentID"]).to_dict()

# --- Uses text ---
usage["Uses"] = usage.apply(
    lambda r: f"{craft_map.get(r['CraftableID'], 'Unknown')} ({int(r['UsageQuantity'])}x)"
    if not pd.isna(r["UsageQuantity"]) else "", axis=1)
uses_joined = usage.groupby("ComponentID")["Uses"].apply(lambda x: ", ".join(x)).rename("Used In")

# --- Locations ---
comp_loc["FoundIn"] = comp_loc["LocationID"].map(loc_map)
found_in = comp_loc.groupby("ComponentID")["FoundIn"].apply(lambda x: ", ".join(sorted(set(x)))).rename("Found In")

# --- Dismantles ---
dis["ResultName"] = dis["ResultComponentID"].map(comp_map)
dis["DismantlesInto"] = dis.apply(
    lambda r: f"{r['ResultName']} ({int(r['Quantity'])}x)" if not pd.isna(r["Quantity"]) else "", axis=1)
dismantles_joined = dis.groupby("SourceComponentID")["DismantlesInto"].apply(lambda x: ", ".join(x)).rename("Dismantles Into")

# --- Merge everything ---
df = comp.merge(uses_joined, how="left", left_on="ComponentID", right_index=True)
df = df.merge(found_in, how="left", left_on="ComponentID", right_index=True)
df = df.merge(dismantles_joined, how="left", left_on="ComponentID", right_index=True)

# --- Fill unknowns ---
df["Used In"] = df["Used In"].fillna("No known use")
df["Found In"] = df["Found In"].fillna("Unknown")
df["Dismantles Into"] = df["Dismantles Into"].fillna("Cannot be dismantled")

# --- Sidebar filters ---
st.sidebar.header("Filters")
rarities = ["All"] + sorted(df["Rarity"].dropna().unique().tolist())
locations = ["All"] + sorted(loc["LocationName"].dropna().unique().tolist()) + ["Unknown"]

rarity_choice = st.sidebar.selectbox("Rarity", rarities)
location_choice = st.sidebar.selectbox("Location", locations)
show_unknown = st.sidebar.checkbox("Show unknown locations", value=True)

# --- Filtering ---
filtered = df.copy()
if rarity_choice != "All":
    filtered = filtered[filtered["Rarity"] == rarity_choice]
if location_choice != "All":
    if location_choice == "Unknown":
        filtered = filtered[filtered["Found In"] == "Unknown"]
    else:
        filtered = filtered[filtered["Found In"].str.contains(location_choice, na=False)]
if not show_unknown:
    filtered = filtered[filtered["Found In"] != "Unknown"]

# --- Display count ---
st.markdown(f"**Results:** {len(filtered)} components")

# --- AG Grid setup ---
gb = GridOptionsBuilder.from_dataframe(filtered)
gb.configure_default_column(
    wrapText=True,
    autoHeight=True,
    resizable=True,
    sortable=True,
    filter=True
)
gb.configure_pagination(enabled=True, paginationAutoPageSize=False, paginationPageSize=25)
grid_options = gb.build()

st.markdown("### Component Browser")
AgGrid(
    filtered,
    gridOptions=grid_options,
    update_mode=GridUpdateMode.NO_UPDATE,
    allow_unsafe_jscode=True,
    height=650,
    fit_columns_on_grid_load=True
)

# --- CSV download ---
csv = filtered.to_csv(index=False).encode("utf-8")
st.download_button("Download filtered results as CSV", data=csv, file_name="components_filtered.csv", mime="text/csv")

# --- Optional: styled rarity preview table ---
st.markdown("### Rarity Color Legend")
legend = pd.DataFrame(list(RARITY_COLORS.items()), columns=["Rarity", "Color"])
st.dataframe(legend.style.applymap(lambda c: f"background-color:{RARITY_COLORS.get(c, '')};" if c in RARITY_COLORS else ""))
