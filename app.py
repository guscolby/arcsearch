# app.py
import io
import pandas as pd
import streamlit as st
from urllib.request import urlopen

st.set_page_config(layout="wide", page_title="Arc Raiders - Component Browser")

# ---------- CONFIG ----------
# Replace this with your own file URL if needed; the one below is the direct-download link you provided.
DRIVE_XLSX_URL = "https://drive.google.com/uc?export=download&id=1Apc99-HAgPTVRAGD2PpaEV4A78JKxN42"
# ----------------------------

@st.cache_data(ttl=300)
def load_workbook(url: str):
    # read the entire workbook into a dict of DataFrames
    # use urlopen to ensure a bytes-like object for pandas
    r = urlopen(url)
    data = r.read()
    xlsx = pd.read_excel(io.BytesIO(data), sheet_name=None, engine="openpyxl")
    return xlsx

def prepare_tables(xlsx: dict):
    # Normalize sheet keys to expected names (strip whitespace)
    # We expect these sheets from your workbook:
    # '01_Craftable', '02_Location', '03_Component', '04_ComponentUsage',
    # '05_ComponentLocation', '06_DismantleResults', 'PowerDashboard'
    craft_df = xlsx.get("01_Craftable", pd.DataFrame()).copy()
    loc_df = xlsx.get("02_Location", pd.DataFrame()).copy()
    comp_df = xlsx.get("03_Component", pd.DataFrame()).copy()
    usage_df = xlsx.get("04_ComponentUsage", pd.DataFrame()).copy()
    comp_loc_df = xlsx.get("05_ComponentLocation", pd.DataFrame()).copy()
    dis_df = xlsx.get("06_DismantleResults", pd.DataFrame()).copy()

    # Ensure consistent column names if Excel had odd whitespace
    craft_df.columns = [str(c).strip() for c in craft_df.columns]
    loc_df.columns = [str(c).strip() for c in loc_df.columns]
    comp_df.columns = [str(c).strip() for c in comp_df.columns]
    usage_df.columns = [str(c).strip() for c in usage_df.columns]
    comp_loc_df.columns = [str(c).strip() for c in comp_loc_df.columns]
    dis_df.columns = [str(c).strip() for c in dis_df.columns]

    # Lower-level convenience: rename common columns to stable names if needed
    # Try to map expected names, but don't force — use what's present
    # Expected names observed in workbook:
    # CraftableID, CraftableName
    # LocationID, LocationName
    # ComponentID, ComponentName, ComponentRarity, ComponentSellPrice
    # ComponentUsage: ComponentID, CraftableID, UsageQuantity
    # ComponentLocation: ComponentID, LocationID
    # DismantleResults: SourceComponentID, ResultComponentID, Quantity

    return {
        "craft": craft_df,
        "loc": loc_df,
        "comp": comp_df,
        "usage": usage_df,
        "comp_loc": comp_loc_df,
        "dis": dis_df
    }

def build_display_df(tables: dict):
    craft = tables["craft"]
    loc = tables["loc"]
    comp = tables["comp"]
    usage = tables["usage"]
    comp_loc = tables["comp_loc"]
    dis = tables["dis"]

    # safe column references (pull by name if present)
    # define fallback column names in case input differs slightly
    def col(df, candidates):
        for c in candidates:
            if c in df.columns:
                return c
        return None

    # map expected columns
    comp_id_col = col(comp, ["ComponentID", "Component Id", "ID", "componentid"])
    comp_name_col = col(comp, ["ComponentName", "Component Name", "Name"])
    comp_rarity_col = col(comp, ["ComponentRarity", "Rarity"])
    comp_price_col = col(comp, ["ComponentSellPrice", "Sell Price", "Price"])

    craft_id_col = col(craft, ["CraftableID", "Craftable Id", "CraftableID"])
    craft_name_col = col(craft, ["CraftableName", "Craftable Name", "Name"])

    loc_id_col = col(loc, ["LocationID", "Location Id", "LocationID"])
    loc_name_col = col(loc, ["LocationName", "Location Name", "Name"])

    usage_comp_id = col(usage, ["ComponentID", "Component Id", "ComponentID"])
    usage_craft_id = col(usage, ["CraftableID", "Craftable Id", "CraftableID"])
    usage_qty_col = col(usage, ["UsageQuantity", "Usage Quantity", "Quantity", "Qty"])

    comp_loc_compid = col(comp_loc, ["ComponentID", "Component Id", "ComponentID"])
    comp_loc_locid = col(comp_loc, ["LocationID", "Location Id", "LocationID"])

    dis_src_col = col(dis, ["SourceComponentID", "Source Component ID", "SourceComponentID"])
    dis_res_col = col(dis, ["ResultComponentID", "Result Component ID", "ResultComponentID"])
    dis_qty_col = col(dis, ["Quantity", "Qty", "quantity"])

    # Create safe copies and ensure the ID columns exist
    # If a required column is missing, create empty placeholder
    if comp_id_col is None or comp_name_col is None:
        st.error("Couldn't find Component ID or Component Name columns in the workbook '03_Component' sheet.")
        st.stop()

    comp_clean = comp[[comp_id_col, comp_name_col] + ([comp_rarity_col] if comp_rarity_col else []) + ([comp_price_col] if comp_price_col else [])].copy()
    comp_clean.columns = ["ComponentID", "ComponentName"] + (["ComponentRarity"] if comp_rarity_col else []) + (["ComponentSellPrice"] if comp_price_col else [])

    # Usage: compute total needed and usage text
    if usage_comp_id and usage_craft_id:
        # map craftable names if available
        craft_map = {}
        if craft_id_col and craft_name_col:
            craft_map = pd.Series(craft[craft_name_col].values,index=craft[craft_id_col]).to_dict()

        usage_valid = usage[[usage_comp_id, usage_craft_id] + ([usage_qty_col] if usage_qty_col else [])].copy()
        usage_valid.columns = ["ComponentID", "CraftableID"] + (["UsageQuantity"] if usage_qty_col else ["UsageQuantity"])
        # ensure numeric
        usage_valid["UsageQuantity"] = pd.to_numeric(usage_valid["UsageQuantity"], errors="coerce").fillna(0)

        total_needed = usage_valid.groupby("ComponentID")["UsageQuantity"].sum().rename("TotalNeeded")
        # build usage strings per component
        def build_usage_text(g):
            rows = []
            for _, r in g.iterrows():
                cname = craft_map.get(r["CraftableID"], str(r["CraftableID"]))
                rows.append(f"{cname} ({int(r['UsageQuantity']) if r['UsageQuantity'].is_integer() else r['UsageQuantity']})")
            return ", ".join(rows) if rows else "No known use"
        usage_text = usage_valid.groupby("ComponentID").apply(build_usage_text).rename("Uses")
    else:
        total_needed = pd.Series(dtype=float, name="TotalNeeded")
        usage_text = pd.Series(dtype=str, name="Uses")

    # Locations: build joined location names per component
    if comp_loc_compid and comp_loc_locid and loc_id_col and loc_name_col:
        # map location id -> name
        loc_map = pd.Series(loc[loc_name_col].values, index=loc[loc_id_col]).to_dict()
        comp_loc_valid = comp_loc[[comp_loc_compid, comp_loc_locid]].copy()
        comp_loc_valid.columns = ["ComponentID", "LocationID"]

        def build_loc_text(g):
            rows = []
            for _, r in g.iterrows():
                lname = loc_map.get(r["LocationID"], str(r["LocationID"]))
                rows.append(lname)
            return ", ".join(sorted(set(rows))) if rows else ""
        loc_text = comp_loc_valid.groupby("ComponentID").apply(build_loc_text).rename("FoundIn")
        # also build boolean HasKnownLoc
        has_known_loc = comp_loc_valid.groupby("ComponentID").size().rename("HasKnownLoc").apply(lambda x: True)
    else:
        loc_text = pd.Series(dtype=str, name="FoundIn")
        has_known_loc = pd.Series(dtype=bool, name="HasKnownLoc")

    # Dismantles: for each SourceComponentID, list (ResultName (qty))
    if dis_src_col and dis_res_col:
        # result name map from comp
        res_map = pd.Series(comp[comp_name_col].values, index=comp[comp_id_col]).to_dict()
        dis_valid = dis[[dis_src_col, dis_res_col] + ([dis_qty_col] if dis_qty_col else [])].copy()
        dis_valid.columns = ["SourceComponentID", "ResultComponentID"] + (["Quantity"] if dis_qty_col else ["Quantity"])
        dis_valid["Quantity"] = pd.to_numeric(dis_valid["Quantity"], errors="coerce").fillna(0)

        def build_dis_text(g):
            rows = []
            for _, r in g.iterrows():
                rname = res_map.get(r["ResultComponentID"], str(r["ResultComponentID"]))
                rows.append(f"{rname} ({int(r['Quantity']) if r['Quantity'].is_integer() else r['Quantity']}x)")
            return ", ".join(rows) if rows else "Cannot be dismantled"
        dis_text = dis_valid.groupby("SourceComponentID").apply(build_dis_text).rename("DismantlesInto")
        # Also allow reverse lookup: components that dismantle into X
        dismantle_lookup = dis_valid[["SourceComponentID", "ResultComponentID"]].copy()
    else:
        dis_text = pd.Series(dtype=str, name="DismantlesInto")
        dismantle_lookup = pd.DataFrame(columns=["SourceComponentID", "ResultComponentID"])

    # join results to master comp table
    out = comp_clean.set_index("ComponentID").copy()
    out = out.join(total_needed).join(usage_text).join(loc_text).join(dis_text)
    # fill missing columns with sensible defaults
    out["TotalNeeded"] = out["TotalNeeded"].fillna(0).astype(int)
    out["Uses"] = out["Uses"].fillna("No known use")
    out["FoundIn"] = out["FoundIn"].fillna("Unknown")
    out["DismantlesInto"] = out["DismantlesInto"].fillna("Cannot be dismantled")
    out.reset_index(inplace=True)

    # prepare helper structures for filters
    rarities = sorted(out["ComponentRarity"].dropna().unique().tolist()) if "ComponentRarity" in out.columns else []
    locations = sorted(loc[loc_name_col].dropna().unique().tolist()) if loc_name_col and loc_name_col in loc.columns else []
    craftables = craft[craft_name_col].dropna().unique().tolist() if craft_name_col and craft_name_col in craft.columns else []
    dismantle_targets = comp_clean["ComponentName"].dropna().unique().tolist()

    # Also prepare a mapping for dismantle filtering: for each source component, list result ids
    # We'll return dis_valid and dismantle_lookup for filtering later
    return {
        "display": out,
        "rarities": rarities,
        "locations": locations,
        "craftables": craftables,
        "dismantle_targets": dismantle_targets,
        "dismantle_lookup": dismantle_lookup
    }

def filter_display(df_display: pd.DataFrame, dismantle_lookup: pd.DataFrame, filters: dict):
    # filters: rarity (str or ""), location (str or ""), craftable (str or ""), dismantle_to (str or ""), show_unknown (bool)
    out = df_display.copy()
    # Rarity
    if filters.get("rarity"):
        out = out[out["ComponentRarity"] == filters["rarity"]]

    # Location filter: if a location is selected, keep only components whose FoundIn contains that text
    if filters.get("location"):
        # note: "FoundIn" is a comma-joined string of location names
        target = filters["location"]
        out = out[out["FoundIn"].str.contains(target, na=False)]

    # Craftable (Used In) filter: find components for which Uses contains the craftable name
    if filters.get("craftable"):
        target = filters["craftable"]
        out = out[out["Uses"].str.contains(target, na=False)]

    # Dismantle filter: user selects a component name that appears as a ResultComponent.
    # We need to find ComponentIDs which have entries in dismantle_lookup where ResultComponentID maps to that component name.
    if filters.get("dismantle_to"):
        # need to map name -> ComponentID; assume df_display has ComponentID/ComponentName
        name_to_id = pd.Series(df_display["ComponentID"].values, index=df_display["ComponentName"]).to_dict()
        dest_name = filters["dismantle_to"]
        dest_id = name_to_id.get(dest_name)
        if dest_id is not None:
            # find SourceComponentIDs that produce dest_id
            matches = dismantle_lookup[dismantle_lookup["ResultComponentID"] == dest_id]["SourceComponentID"].unique().tolist()
            out = out[out["ComponentID"].isin(matches)]
        else:
            # If not found, no results
            out = out.iloc[0:0]

    # Show unknown toggle: if False, drop rows where FoundIn == "Unknown"
    if not filters.get("show_unknown", True):
        out = out[out["FoundIn"].fillna("Unknown") != "Unknown"]

    return out

# ---- App UI ----
st.title("Arc Raiders — Component Browser")
st.markdown("An interactive view of the component database. Filters mimic the PowerDashboard logic.")

# Load workbook
with st.spinner("Loading workbook from Google Drive..."):
    xlsx = load_workbook(DRIVE_XLSX_URL)

tables = prepare_tables(xlsx)
prepared = build_display_df(tables)
df_display = prepared["display"]
dismantle_lookup = prepared["dismantle_lookup"]

# Sidebar filters
st.sidebar.header("Filters")
rarity_choice = st.sidebar.selectbox("Rarity", options=["All"] + prepared["rarities"], index=0)
location_choice = st.sidebar.selectbox("Location", options=["All"] + prepared["locations"] + ["Unknown"], index=0)
craft_choice = st.sidebar.selectbox("Used In (Craftable)", options=["All"] + prepared["craftables"], index=0)
dismantle_choice = st.sidebar.selectbox("Dismantles To (component)", options=["All"] + prepared["dismantle_targets"], index=0)
show_unknown = st.sidebar.checkbox("Show items with unknown location", value=True)

# Build filter dict
filters = {}
if rarity_choice and rarity_choice != "All":
    filters["rarity"] = rarity_choice
if location_choice and location_choice != "All":
    filters["location"] = location_choice
if craft_choice and craft_choice != "All":
    filters["craftable"] = craft_choice
if dismantle_choice and dismantle_choice != "All":
    filters["dismantle_to"] = dismantle_choice
filters["show_unknown"] = show_unknown

# Apply filters
result_df = filter_display(df_display, dismantle_lookup, filters)

# Display summary and table
st.markdown(f"**Results:** {len(result_df)} components")
st.dataframe(result_df[[
    "ComponentName",
    "ComponentRarity",
    "ComponentSellPrice",
    "TotalNeeded",
    "Uses",
    "FoundIn",
    "DismantlesInto"
]].rename(columns={
    "ComponentName": "Name",
    "ComponentRarity": "Rarity",
    "ComponentSellPrice": "Sell Price",
    "TotalNeeded": "Total Needed",
    "Uses": "Used In",
    "FoundIn": "Found In",
    "DismantlesInto": "Dismantles Into"
}), height=600)

# CSV download
@st.cache_data
def convert_df_to_csv(df: pd.DataFrame):
    return df.to_csv(index=False).encode("utf-8")

csv = convert_df_to_csv(result_df)
st.download_button("Download filtered results as CSV", data=csv, file_name="components_filtered.csv", mime="text/csv")
