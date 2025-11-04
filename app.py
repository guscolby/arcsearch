# app.py
import io
import pandas as pd
import streamlit as st
from urllib.request import urlopen
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

# ---------- CONFIG ----------
GITHUB_XLSX_RAW = "https://raw.githubusercontent.com/guscolby/arcsearch/main/ARC%20RAIDERS%20MATS.xlsx"
st.set_page_config(layout="wide", page_title="Arc Raiders - Component Browser")
# ----------------------------

st.title("🔎 Arc Raiders — Component Browser (Live from GitHub)")

# helper to pick a column name from a list of candidates
def pick_col(df, candidates):
    if df is None:
        return None
    cols = [c for c in df.columns]
    for cand in candidates:
        for c in cols:
            if str(c).strip().lower() == cand.strip().lower():
                return c
    # fallback: find by substring
    for cand in candidates:
        cl = cand.strip().lower()
        for c in cols:
            if cl in str(c).strip().lower():
                return c
    return None

@st.cache_data(ttl=300)
def load_workbook_from_github(raw_url):
    # read bytes from raw GitHub URL
    b = urlopen(raw_url).read()
    xls = pd.read_excel(io.BytesIO(b), sheet_name=None, engine="openpyxl")
    return xls

def prepare_data(xls_dict):
    # load sheets (if missing, use empty df)
    craft = xls_dict.get("01_Craftable", pd.DataFrame()).copy()
    loc = xls_dict.get("02_Location", pd.DataFrame()).copy()
    comp = xls_dict.get("03_Component", pd.DataFrame()).copy()
    usage = xls_dict.get("04_ComponentUsage", pd.DataFrame()).copy()
    comp_loc = xls_dict.get("05_ComponentLocation", pd.DataFrame()).copy()
    dis = xls_dict.get("06_DismantleResults", pd.DataFrame()).copy()

    # standardize column names by stripping whitespace
    for df in [craft, loc, comp, usage, comp_loc, dis]:
        df.columns = [str(c).strip() for c in df.columns]

    # identify columns using tolerant matching
    craft_id_col = pick_col(craft, ["CraftableID", "Craftable Id", "Craftable Id"])
    craft_name_col = pick_col(craft, ["CraftableName", "Craftable Name", "Name"])

    loc_id_col = pick_col(loc, ["LocationID", "Location Id", "Location Id"])
    loc_name_col = pick_col(loc, ["LocationName", "Location Name", "Name"])

    comp_id_col = pick_col(comp, ["ComponentID", "Component Id", "ComponentID"])
    comp_name_col = pick_col(comp, ["ComponentName", "Component Name", "Name"])
    comp_rarity_col = pick_col(comp, ["ComponentRarity", "Rarity"])
    comp_price_col = pick_col(comp, ["ComponentSellPrice", "Sell Price", "Price"])

    usage_comp_col = pick_col(usage, ["ComponentID", "Component Id"])
    usage_craft_col = pick_col(usage, ["CraftableID", "Craftable Id"])
    usage_qty_col = pick_col(usage, ["UsageQuantity", "Usage Quantity", "Quantity", "Qty"])

    comp_loc_compid = pick_col(comp_loc, ["ComponentID"])
    comp_loc_locid = pick_col(comp_loc, ["LocationID"])

    dis_src_col = pick_col(dis, ["SourceComponentID", "SourceComponent", "Source Component ID"])
    dis_res_col = pick_col(dis, ["ResultComponentID", "ResultComponent", "Result Component ID"])
    dis_qty_col = pick_col(dis, ["Quantity", "Qty"])

    # sanity checks for required columns
    required = {
        "components": (comp_id_col, comp_name_col),
        "locations": (loc_id_col, loc_name_col),
    }
    for name, (a,b) in required.items():
        if a is None or b is None:
            st.error(f"Required columns not found in sheet for '{name}'. Found columns are:\n\nComponents: {list(comp.columns)}\nLocations: {list(loc.columns)}")
            st.stop()

    # rename columns in working copies to stable names
    comp = comp.rename(columns={comp_id_col: "ComponentID", comp_name_col: "ComponentName"})
    if comp_rarity_col:
        comp = comp.rename(columns={comp_rarity_col: "ComponentRarity"})
    else:
        comp["ComponentRarity"] = pd.NA
    if comp_price_col:
        comp = comp.rename(columns={comp_price_col: "ComponentSellPrice"})
    else:
        comp["ComponentSellPrice"] = pd.NA

    if craft_id_col and craft_name_col:
        craft = craft.rename(columns={craft_id_col: "CraftableID", craft_name_col: "CraftableName"})
    else:
        craft = craft.rename(columns={c: c for c in craft.columns})

    if loc_id_col and loc_name_col:
        loc = loc.rename(columns={loc_id_col: "LocationID", loc_name_col: "LocationName"})
    else:
        loc = loc.rename(columns={c: c for c in loc.columns})

    if usage_comp_col and usage_craft_col:
        usage = usage.rename(columns={usage_comp_col: "ComponentID", usage_craft_col: "CraftableID"})
        if usage_qty_col:
            usage = usage.rename(columns={usage_qty_col: "UsageQuantity"})
        else:
            usage["UsageQuantity"] = 1
    else:
        usage = pd.DataFrame(columns=["ComponentID","CraftableID","UsageQuantity"])

    if comp_loc_compid and comp_loc_locid:
        comp_loc = comp_loc.rename(columns={comp_loc_compid: "ComponentID", comp_loc_locid: "LocationID"})
    else:
        comp_loc = pd.DataFrame(columns=["ComponentID","LocationID"])

    if dis_src_col and dis_res_col:
        dis = dis.rename(columns={dis_src_col: "SourceComponentID", dis_res_col: "ResultComponentID"})
        if dis_qty_col:
            dis = dis.rename(columns={dis_qty_col: "Quantity"})
        else:
            dis["Quantity"] = 1
    else:
        dis = pd.DataFrame(columns=["SourceComponentID","ResultComponentID","Quantity"])

    # ensure numeric where appropriate
    usage["UsageQuantity"] = pd.to_numeric(usage.get("UsageQuantity", pd.Series(dtype=float)), errors="coerce").fillna(0)
    dis["Quantity"] = pd.to_numeric(dis.get("Quantity", pd.Series(dtype=float)), errors="coerce").fillna(0)

    # Merge comp_loc with loc to get LocationName
    if not comp_loc.empty and "LocationID" in comp_loc.columns and not loc.empty:
        comp_loc = comp_loc.merge(loc[["LocationID","LocationName"]], on="LocationID", how="left")
        # build Found In text
        found_in = comp_loc.groupby("ComponentID")["LocationName"].apply(lambda s: ", ".join(sorted(set([v for v in s.dropna()])))).rename("Found In")
        has_known_loc = comp_loc.groupby("ComponentID").size().rename("HasKnownLoc").apply(lambda x: True)
    else:
        found_in = pd.Series(dtype=str, name="Found In")
        has_known_loc = pd.Series(dtype=bool, name="HasKnownLoc")

    # Build Uses text & TotalNeeded
    if not usage.empty and "ComponentID" in usage.columns and "CraftableID" in usage.columns:
        # merge craftable names where possible
        if "CraftableID" in craft.columns and "CraftableName" in craft.columns:
            usage = usage.merge(craft[["CraftableID","CraftableName"]], on="CraftableID", how="left")
            usage["CraftableName"] = usage["CraftableName"].fillna(usage["CraftableID"].astype(str))
        else:
            usage["CraftableName"] = usage["CraftableID"].astype(str)
        usage["UsageQuantity"] = pd.to_numeric(usage["UsageQuantity"], errors="coerce").fillna(0)
        total_needed = usage.groupby("ComponentID")["UsageQuantity"].sum().rename("TotalNeeded")
        uses_text = usage.groupby("ComponentID").apply(lambda g: ", ".join([f"{row['CraftableName']} ({int(row['UsageQuantity'])}x)" if (pd.notna(row['UsageQuantity']) and float(row['UsageQuantity']).is_integer()) else f"{row['CraftableName']} ({row['UsageQuantity']})" for _,row in g.iterrows()])).rename("Used In")
    else:
        total_needed = pd.Series(dtype=float, name="TotalNeeded")
        uses_text = pd.Series(dtype=str, name="Used In")

    # Dismantles text (source -> list of result names with qty)
    if not dis.empty and "SourceComponentID" in dis.columns and "ResultComponentID" in dis.columns:
        # map result id -> name using components table
        id_to_name = pd.Series(comp["ComponentName"].values, index=comp["ComponentID"]).to_dict()
        dis["ResultName"] = dis["ResultComponentID"].map(id_to_name).fillna(dis["ResultComponentID"].astype(str))
        dis_text = dis.groupby("SourceComponentID").apply(lambda g: ", ".join([f"{r['ResultName']} ({int(r['Quantity'])}x)" if (pd.notna(r['Quantity']) and float(r['Quantity']).is_integer()) else f"{r['ResultName']} ({r['Quantity']})" for _,r in g.iterrows()])).rename("Dismantles Into")
        dismantle_lookup = dis[["SourceComponentID","ResultComponentID"]].copy()
    else:
        dis_text = pd.Series(dtype=str, name="Dismantles Into")
        dismantle_lookup = pd.DataFrame(columns=["SourceComponentID","ResultComponentID"])

    # Assemble display dataframe
    display_df = comp.set_index("ComponentID").copy()
    display_df = display_df.join(total_needed).join(uses_text).join(found_in).join(dis_text)
    display_df = display_df.reset_index()

    # fill defaults
    display_df["TotalNeeded"] = display_df["TotalNeeded"].fillna(0).astype(int)
    display_df["Used In"] = display_df["Used In"].fillna("No known use")
    display_df["Found In"] = display_df["Found In"].fillna("Unknown")
    display_df["Dismantles Into"] = display_df["Dismantles Into"].fillna("Cannot be dismantled")

    return {
        "display": display_df,
        "dismantle_lookup": dismantle_lookup,
        "location_list": sorted(loc["LocationName"].dropna().unique().tolist()) if not loc.empty else [],
        "rarity_list": sorted(display_df["ComponentRarity"].dropna().unique().tolist()) if "ComponentRarity" in display_df.columns else []
    }

# Load workbook
with st.spinner("Loading workbook from GitHub..."):
    try:
        xls = load_workbook_from_github(GITHUB_XLSX_RAW)
    except Exception as e:
        st.error(f"Could not load workbook from GitHub URL: {e}")
        st.stop()

prepared = prepare_data(xls)
df_display = prepared["display"]
dismantle_lookup = prepared["dismantle_lookup"]
location_list = prepared["location_list"]
rarity_list = prepared["rarity_list"]

# Sidebar controls
st.sidebar.header("Filters")
search_text = st.sidebar.text_input("Search by name (substring)", value="")
rarity_choice = st.sidebar.selectbox("Rarity", ["All"] + rarity_list)
location_choice = st.sidebar.selectbox("Location", ["All"] + location_list + ["Unknown"])
dismantle_choice = st.sidebar.selectbox("Dismantles To", ["All"] + sorted(df_display["ComponentName"].dropna().unique().tolist()))
show_unknown = st.sidebar.checkbox("Show items with unknown location", value=True)

# Apply filters
df_filtered = df_display.copy()

if search_text:
    df_filtered = df_filtered[df_filtered["ComponentName"].str.contains(search_text, case=False, na=False)]

if rarity_choice and rarity_choice != "All":
    df_filtered = df_filtered[df_filtered["ComponentRarity"] == rarity_choice]

if location_choice and location_choice != "All":
    if location_choice == "Unknown":
        df_filtered = df_filtered[df_filtered["Found In"] == "Unknown"]
    else:
        df_filtered = df_filtered[df_filtered["Found In"].str.contains(location_choice, na=False)]

if not show_unknown:
    df_filtered = df_filtered[df_filtered["Found In"] != "Unknown"]

# Dismantle filter: find components whose SourceComponentID produces chosen result
if dismantle_choice and dismantle_choice != "All":
    name_to_id = pd.Series(df_display["ComponentID"].values, index=df_display["ComponentName"]).to_dict()
    dest_id = name_to_id.get(dismantle_choice)
    if dest_id is not None and not dismantle_lookup.empty:
        matches = dismantle_lookup[dismantle_lookup["ResultComponentID"] == dest_id]["SourceComponentID"].unique().tolist()
        df_filtered = df_filtered[df_filtered["ComponentID"].isin(matches)]
    else:
        df_filtered = df_filtered.iloc[0:0]

st.markdown(f"**Results:** {len(df_filtered)} components")

# Rarity color mapping
RARITY_COLORS = {
    "Green": "#4CAF50",
    "Blue": "#2196F3",
    "Purple": "#9C27B0",
    "Orange": "#FF9800",
    "Legendary": "#FFB300",
    "Common": "#9E9E9E",
    "Uncommon": "#4CAF50",
    "Rare": "#2196F3",
    "Epic": "#9C27B0"
}

# create a display column for colored rarity (HTML)
def rarity_badge(r):
    if pd.isna(r):
        return ""
    color = RARITY_COLORS.get(str(r), "")
    if color:
        return f"<div style='background:{color};color:white;padding:4px;border-radius:4px;text-align:center;font-weight:600'>{r}</div>"
    return str(r)

df_filtered["RarityBadge"] = df_filtered["ComponentRarity"].apply(rarity_badge)

# Prepare AG Grid
display_cols = ["ComponentName", "RarityBadge", "ComponentSellPrice", "TotalNeeded", "Used In", "Found In", "Dismantles Into"]
grid_df = df_filtered[display_cols].rename(columns={
    "ComponentName": "Name",
    "RarityBadge": "Rarity",
    "ComponentSellPrice": "Sell Price",
    "TotalNeeded": "Total Needed"
})

# Build grid options
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

# Render AgGrid
AgGrid(
    results,
    gridOptions=grid_options,
    height=500,
    theme="streamlit",
    update_mode=GridUpdateMode.SELECTION_CHANGED,
)

# CSV download
@st.cache_data
def df_to_csv_bytes(df):
    return df.to_csv(index=False).encode("utf-8")

csv_bytes = df_to_csv_bytes(df_filtered.drop(columns=["RarityBadge"], errors="ignore"))
st.download_button("Download filtered results as CSV", data=csv_bytes, file_name="arc_components_filtered.csv", mime="text/csv")

