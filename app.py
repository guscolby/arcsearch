import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

st.set_page_config(page_title="ARC Raiders Materials Search", layout="wide")
st.title("🔍 ARC Raiders Materials Search")
st.caption("Interactive search across all components, crafting, and dismantle data.")

# ---------------------------------------------------------
# LOAD DATA
# ---------------------------------------------------------
@st.cache_data
def load_data():
    url = "https://raw.githubusercontent.com/guscolby/arcsearch/main/ARC%20RAIDERS%20MATS.xlsx"
    xls = pd.ExcelFile(url)

    tbl_comp = pd.read_excel(xls, "tblComponent")
    tbl_loc = pd.read_excel(xls, "tblLocation")
    tbl_comp_loc = pd.read_excel(xls, "tblComponentLocation")
    tbl_dismantle = pd.read_excel(xls, "tblDismantleResults")
    tbl_craftable = pd.read_excel(xls, "tblCraftable")
    tbl_usage = pd.read_excel(xls, "tblComponentUsage")

    # ---- Merge location names ----
    comp_loc = tbl_comp_loc.merge(tbl_loc, on="LocationID", how="left")

    # ---- Aggregate known locations ----
    found_in = (
        comp_loc.groupby("ComponentID")["LocationName"]
        .apply(lambda x: ", ".join(sorted(set(x.dropna()))))
        .rename("Location")
        .reset_index()
    )

    # ---- Aggregate dismantle results ----
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
                f"{q}x {n}"
                for q, n in zip(x["Quantity"], x["ComponentName_Result"])
                if pd.notna(n)
            )
        )
        .rename("Recycles To")
        .reset_index()
    )

    # ---- Aggregate usage (crafting recipes) ----
    uses = (
        tbl_usage.merge(
            tbl_craftable[["CraftableID", "CraftableName"]],
            on="CraftableID",
            how="left",
        )
        .groupby("ComponentID")
        .apply(
            lambda x: ", ".join(
                f"{n} ({q}x)" for n, q in zip(x["CraftableName"], x["UsageQuantity"]) if pd.notna(n)
            )
        )
        .rename("Used In")
        .reset_index()
    )

    # ---- Merge everything together ----
    merged = (
        tbl_comp.merge(found_in, on="ComponentID", how="left")
        .merge(dismantles, left_on="ComponentID", right_on="SourceComponentID", how="left")
        .merge(uses, on="ComponentID", how="left")
    )

    # ---- Clean & format ----
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
    st.header("Search Filters")
    search_query = st.text_input("Search item name:", "")
    show_unknown = st.checkbox("Show items with unknown location", value=True)

# ---------------------------------------------------------
# APPLY FILTERS
# ---------------------------------------------------------
filtered = merged_df.copy()

if search_query:
    filtered = filtered[filtered["Name"].str.contains(search_query, case=False, na=False)]

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
if not results.empty:
    st.markdown(f"### Search Results ({len(results)} items found)")

    gb = GridOptionsBuilder.from_dataframe(results)
    gb.configure_pagination(enabled=True)
    gb.configure_default_column(
        groupable=False,
        value=True,
        enableRowGroup=False,
        enablePivot=False,
        enableValue=True,
        wrapText=True,
        autoHeight=True,
    )
    gb.configure_selection('single')
    grid_options = gb.build()

    AgGrid(
        results,
        gridOptions=grid_options,
        height=600,
        theme="streamlit",
        update_mode=GridUpdateMode.SELECTION_CHANGED,
    )

else:
    st.warning("No matching items found. Try adjusting your search or filters.")
