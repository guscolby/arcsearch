import streamlit as st
import pandas as pd
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

# ---------------------------------------------------------
# APP CONFIG
# ---------------------------------------------------------
st.set_page_config(page_title="ARC Raiders Materials Search", layout="wide")
st.title("🔍 ARC Raiders Materials Search")
st.caption("Interactive browser for ARC Raiders components, crafting uses, and dismantle results.")

# ---------------------------------------------------------
# LOAD DATA
# ---------------------------------------------------------
@st.cache_data
def load_data():
    """Load and merge data from Excel file hosted on GitHub"""
    url = "https://raw.githubusercontent.com/guscolby/arcsearch/main/ARC%20RAIDERS%20MATS.xlsx"
    
    try:
        xls = pd.ExcelFile(url)
        
        # Load all sheets using indexes
        tbl_craftable = pd.read_excel(xls, 1)    # Craftable items sheet
        tbl_loc = pd.read_excel(xls, 2)          # Locations sheet
        tbl_comp = pd.read_excel(xls, 3)         # Components sheet
        tbl_usage = pd.read_excel(xls, 4)        # Component usage sheet
        tbl_comp_loc = pd.read_excel(xls, 5)     # Component locations sheet
        tbl_dismantle = pd.read_excel(xls, 6)    # Dismantle results sheet

        # ---- Merge Location Data ----
        # Combine component locations with location names
        comp_loc = tbl_comp_loc.merge(tbl_loc, on="LocationID", how="left")
        
        # Create comma-separated list of locations for each component
        found_in = (
            comp_loc.groupby("ComponentID")["LocationName"]
            .apply(lambda x: ", ".join(sorted(set(x.dropna()))))
            .rename("Location")
            .reset_index()
        )

        # ---- Merge Dismantle Results ----
        # Combine dismantle data with component names to show what items recycle into
        dismantle_merged = tbl_dismantle.merge(
            tbl_comp[["ComponentID", "ComponentName"]],
            left_on="ResultComponentID",
            right_on="ComponentID",
            how="left",
            suffixes=("", "_Result"),
        )
        
        # Find the correct column name for result components
        result_name_col = "ComponentName_Result"
        if result_name_col not in dismantle_merged.columns:
            result_name_col = "ComponentName"
        
        # Create formatted string of dismantle results
        dismantles = (
            dismantle_merged
            .groupby("SourceComponentID")
            .apply(
                lambda x: ", ".join(
                    f"{int(q)}x {n}" if pd.notna(n) and n != "" else ""
                    for q, n in zip(x["Quantity"], x[result_name_col])
                )
            )
            .rename("Recycles To")
            .reset_index()
        )

        # ---- Merge Component Usage (Crafting) ----
        # Combine usage data with craftable item names
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
        # Merge all the prepared data into one comprehensive dataframe
        merged = (
            tbl_comp.merge(found_in, on="ComponentID", how="left")
            .merge(dismantles, left_on="ComponentID", right_on="SourceComponentID", how="left")
            .merge(uses, on="ComponentID", how="left")
        )

        # ---- Clean and Format Data ----
        # Fill missing values with appropriate defaults
        merged["ComponentName"] = merged["ComponentName"].fillna("Unnamed Item")
        merged["ComponentRarity"] = merged["ComponentRarity"].fillna("Unknown")
        merged["ComponentSellPrice"] = merged["ComponentSellPrice"].fillna(0)
        merged["Used In"] = merged["Used In"].fillna("No known use")
        merged["Recycles To"] = merged["Recycles To"].fillna("Cannot be dismantled")
        merged["Location"] = merged["Location"].fillna("Unknown")

        # Select and rename final columns
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
        
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        # Return empty dataframe as fallback
        return pd.DataFrame(columns=["Name", "Rarity", "Sell Price", "Used In", "Recycles To", "Location"])

# Load the data
merged_df = load_data()

# ---------------------------------------------------------
# SIDEBAR FILTERS
# ---------------------------------------------------------
with st.sidebar:
    st.header("🔧 Filters")
    
    # Text search filter - at the top
    search_query = st.text_input("Search item name:", "")
    
    # Dismantle filter - search within "Recycles To" column - second in order
    dismantle_query = st.text_input("Search dismantle results:", "")
    
    # Usage filter - search within "Used In" column - third in order
    usage_query = st.text_input("Search usage (crafting):", "")
    
    # Location filter with "All" option - fourth in order
    # Extract individual locations from comma-separated values
    all_locations = []
    for locations in merged_df["Location"].dropna():
        # Split comma-separated locations and add individual ones
        individual_locs = [loc.strip() for loc in str(locations).split(",")]
        all_locations.extend(individual_locs)
    
    # Get unique individual locations and sort them
    location_options = ["All"] + sorted(set([loc for loc in all_locations if loc and loc != "Unknown"]))
    location_choice = st.selectbox("Location:", location_options)
    
    # Rarity filter with "All" option - fifth in order
    rarity_options = ["All"] + sorted(merged_df["Rarity"].dropna().unique().tolist())
    rarity_choice = st.selectbox("Rarity:", rarity_options)
    
    # Commented out - unknown locations checkbox (not functioning with current dataset)
    # show_unknown = st.checkbox("Show items with unknown location", value=True)

# ---------------------------------------------------------
# FILTERING LOGIC
# ---------------------------------------------------------
filtered = merged_df.copy()

# Apply text search on name
if search_query:
    filtered = filtered[filtered["Name"].str.contains(search_query, case=False, na=False)]

# Apply dismantle search
if dismantle_query:
    filtered = filtered[filtered["Recycles To"].str.contains(dismantle_query, case=False, na=False)]

# Apply usage search
if usage_query:
    filtered = filtered[filtered["Used In"].str.contains(usage_query, case=False, na=False)]

# Apply location filter - check if any individual location matches
if location_choice != "All":
    filtered = filtered[filtered["Location"].str.contains(location_choice, case=False, na=False)]

# Apply rarity filter
if rarity_choice != "All":
    filtered = filtered[filtered["Rarity"] == rarity_choice]

# Commented out - unknown locations filter (not functioning with current dataset)
# if not show_unknown:
#     filtered = filtered[filtered["Location"] != "Unknown"]

results = filtered.copy()

# ---------------------------------------------------------
# DISPLAY RESULTS
# ---------------------------------------------------------
if not results.empty:
    st.markdown(f"### 📊 Results ({len(results)} items found)")
    
    # Configure AG Grid for better display
    grid_df = results[["Name", "Rarity", "Sell Price", "Used In", "Recycles To", "Location"]]
    
    gb = GridOptionsBuilder.from_dataframe(grid_df)
    
    # Configure grid options
    gb.configure_default_column(
        wrapText=True, 
        autoHeight=True, 
        resizable=True, 
        sortable=True, 
        filter=True,
        flex=1
    )
    
    # Set column-specific properties
    gb.configure_column("Name", flex=2, minWidth=150)  # More space for names
    gb.configure_column("Rarity", width=120)
    gb.configure_column("Sell Price", width=100)
    gb.configure_column("Used In", flex=3, minWidth=200)  # More space for usage
    gb.configure_column("Recycles To", flex=3, minWidth=200)  # More space for dismantles
    gb.configure_column("Location", flex=2, minWidth=150)  # More space for locations
    
    # Show all results on one page
    gb.configure_pagination(enabled=False)  # Disable pagination to show all results
    
    grid_options = gb.build()

    # Display the grid
    AgGrid(
        grid_df,
        gridOptions=grid_options,
        allow_unsafe_jscode=True,
        height=min(800, 35 * len(results) + 100),  # Dynamic height based on results
        fit_columns_on_grid_load=False,
        update_mode=GridUpdateMode.NO_UPDATE,
    )

    # CSV download option
    csv_data = results.to_csv(index=False).encode("utf-8")
    st.download_button(
        "💾 Download filtered results as CSV",
        data=csv_data,
        file_name="arc_raiders_filtered.csv",
        mime="text/csv",
    )

else:
    st.warning("🚫 No matching items found. Try adjusting your search or filters.")
