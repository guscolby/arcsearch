import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

# ---------------------------------------------------------
# APP CONFIG
# ---------------------------------------------------------
st.set_page_config(page_title="ARC Raiders Materials Search", layout="wide")
st.title("🔍 ARC Raiders Materials Search (PowerDashboard)")
st.caption("Interactive browser for ARC Raiders components, crafting uses, and dismantle results.")

# ---------------------------------------------------------
# LOAD DATA
# ---------------------------------------------------------
@st.cache_data
def load_data():
    # GitHub raw XLSX URL
    url = "https://raw.githubusercontent.com/guscolby/arcsearch/main/ARC%20RAIDERS%20MATS.xlsx"
        
    xls = pd.ExcelFile(url)
        
    # DEBUG: Print available sheet names
    st.sidebar.write("Available sheets in Excel file:")
    st.sidebar.write(xls.sheet_names)
        
    # Use the actual tab names in your workbook
    # If these don't match, we'll need to adjust based on the actual sheet names
    tbl_craftable = pd.read_excel(xls, "01_Craftable")
    tbl_loc = pd.read_excel(xls, "02_Location")
    tbl_comp = pd.read_excel(xls, "03_Component")
    tbl_usage = pd.read_excel(xls, "04_ComponentUsage")
    tbl_comp_loc = pd.read_excel(xls, "05_ComponentLocation")
    tbl_dismantle = pd.read_excel(xls, "06_DismantleResults")

    # ---- Merge Location Names ----
    comp_loc = tbl_comp_loc.merge(tbl_loc, on="LocationID", how="left")

    found_in = (
        comp_loc.groupby("ComponentID")["LocationName"]
        .apply(lambda x: ", ".join(sorted(set(x.dropna()))))
        .rename("Location")
        .reset_index()
    )

    # ---- Merge Dismantle Results ----
    dismantles = (
        tbl_dismantle.merge(
            tbl_comp[["ComponentID", "ComponentName"]],
            left_on="ResultComponentID",
            right_on="ComponentID",
            how="left",
            suffixes=("", "_Result"),
        )
        .groupby("SourceComponentID")
        .apply(
            lambda x: ", ".join(
                f"{int(q)}x {n}" if pd.notna(n) else ""
                for q, n in zip(x["Quantity"], x["ComponentName_Result"])
            )
        )
        .rename("Recycles To")
        .reset_index()
    )

    # ---- Merge Component Usage (Crafting) ----
    uses = (
        tbl_usage.merge(
            tbl_craftable[["CraftableID", "CraftableName"]],
            on="CraftableID",
            how="left",
        )
        .groupby("ComponentID")
        .apply(
            lambda x: ", ".join(
                f"{n} ({int(q)}x)" if pd.notna(n) else ""
                for n, q in zip(x["CraftableName"], x["UsageQuantity"])
            )
        )
        .rename("Used In")
        .reset_index()
    )

    # ---- Combine All Data ----
    merged = (
        tbl_comp.merge(found_in, on="ComponentID", how="left")
        .merge(dismantles, left_on="ComponentID", right_on="SourceComponentID", how="left")
        .merge(uses, on="ComponentID", how="left")
    )

    # ---- Fill Missing Values ----
    merged["ComponentName"] = merged["ComponentName"].fillna("Unnamed Item")
    merged["ComponentRarity"] = merged["ComponentRarity"].fillna("Unknown")
    merged["ComponentSellPrice"] = merged["ComponentSellPrice"].fillna(0)
    merged["Used In"] = merged["Used In"].fillna("No known use")
    merged["Recycles To"] = merged["Recycles To"].fillna("Cannot be dismantled")
    merged["Location"] = merged["Location"].fillna("Unknown")

    merged = merged[
        [
            "ComponentName",
            "ComponentRarity",
            "ComponentSellPrice",
            "Used In",
            "Recycles To",
            "Location",
        ]
    ]
    merged.columns = ["Name", "Rarity", "Sell Price", "Used In", "Recycles To", "Location"]

    return merged


merged_df = load_data()

# ---------------------------------------------------------
# SIDEBAR FILTERS
# ---------------------------------------------------------
with st.sidebar:
    st.header("Filters")
    search_query = st.text_input("Search item name:", "")
    rarity_options = ["All"] + sorted(merged_df["Rarity"].dropna().unique().tolist())
    rarity_choice = st.selectbox("Rarity:", rarity_options)
    show_unknown = st.checkbox("Show items with unknown location", value=True)

# ---------------------------------------------------------
# FILTERING LOGIC
# ---------------------------------------------------------
filtered = merged_df.copy()

if search_query:
    filtered = filtered[filtered["Name"].str.contains(search_query, case=False, na=False)]

if rarity_choice != "All":
    filtered = filtered[filtered["Rarity"] == rarity_choice]

if not show_unknown:
    filtered = filtered[filtered["Location"] != "Unknown"]

results = filtered.copy()

# ---------------------------------------------------------
# RARITY COLOR STYLING
# ---------------------------------------------------------
rarity_colors = {
    "Common": "#9E9E9E",
    "Uncommon": "#4CAF50",
    "Green": "#4CAF50",
    "Rare": "#2196F3",
    "Blue": "#2196F3",
    "Epic": "#9C27B0",
    "Purple": "#9C27B0",
    "Legendary": "#FF9800",
    "Gold": "#FFB300",
    "Unknown": "#B0BEC5",
}

def rarity_badge(rarity):
    color = rarity_colors.get(str(rarity), "#FFFFFF")
    return f"<div style='background-color:{color};color:white;padding:4px;border-radius:4px;text-align:center;font-weight:600'>{rarity}</div>"

results["Rarity Display"] = results["Rarity"].apply(rarity_badge)

# ---------------------------------------------------------
# DISPLAY RESULTS
# ---------------------------------------------------------
if not results.empty:
    st.markdown(f"### Results ({len(results)} items found)")

    # AG Grid Configuration
    grid_df = results[["Name", "Rarity Display", "Sell Price", "Used In", "Recycles To", "Location"]]
    gb = GridOptionsBuilder.from_dataframe(grid_df)
    gb.configure_default_column(
        wrapText=True, autoHeight=True, resizable=True, sortable=True, filter=True
    )
    gb.configure_pagination(enabled=True, paginationAutoPageSize=False, paginationPageSize=25)
    grid_options = gb.build()

    AgGrid(
        grid_df,
        gridOptions=grid_options,
        allow_unsafe_jscode=True,
        height=650,
        fit_columns_on_grid_load=True,
        update_mode=GridUpdateMode.NO_UPDATE,
    )

    # CSV download
    csv_data = results.drop(columns=["Rarity Display"], errors="ignore").to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download filtered results as CSV",
        data=csv_data,
        file_name="arc_raiders_filtered.csv",
        mime="text/csv",
    )

else:
    st.warning("No matching items found. Try adjusting your search or filters.")

