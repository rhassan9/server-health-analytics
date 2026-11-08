# Power BI Implementation Sequence

Follow these exact steps from raw data extraction to publishing the final Proof-of-Concept marketing dashboard. This guide assumes you have [server_health_summary.xlsx](file:///Users/asta/Downloads/Madan%20B%20Fiverr/Server%20Analysis/server_health_summary.xlsx) downloaded and Power BI Desktop open.

## Phase 1: Data Loading (Power Query)
1. **Get Data**: Click **Get Data** -> **Excel Workbook**.
2. Select your [server_health_summary.xlsx](file:///Users/asta/Downloads/Madan%20B%20Fiverr/Server%20Analysis/server_health_summary.xlsx) file.
3. Check the boxes for all three raw tabs: `Stats`, `Security`, and `Warnings`.
4. Do NOT click Load. Click **Transform Data** to open the Power Query Editor.

## Phase 2: Splitting Time from Date (Crucial Tweak)
Because Power BI requires strict dimensional modeling to cross-filter by the hour perfectly, we must extract the Hour from the `timestamp`.
*Complete these 3 steps exactly for ALL THREE tables (Stats, Security, Warnings):*
1. **Duplicate**: Right-click the `timestamp` column header -> **Duplicate Column**.
2. **Form the Date**: Rename the original `timestamp` column to `Date`. Click the data type calendar icon on the header and change it from *Date/Time* to simply **Date**.
3. **Form the Hour**: Rename the duplicated column to `Hour`. 
   - Click the data type icon and change it to **Time**.
   - Go to the **Transform** ribbon -> click **Time** -> **Hour** -> **Hour**. This strips the minutes/seconds and leaves a clean integer (e.g., `18` for 6:00 PM).
4. Click **Close & Apply** at the top left to load the models into Power BI.

## Phase 3: Dimensional Modeling
1. Go to the **Model View** tab on the far left.
2. Open your [PowerBI_DAX_Formulas.md](file:///Users/asta/.gemini/antigravity/brain/5f48bc47-6ed2-4e6c-b5ab-379353e89224/PowerBI_DAX_Formulas.md) file. Create the two Calculated Tables (`Dim_Calendar` and `Dim_Time`) using the exact DAX provided.
3. **Build the Star Schema Relationships:** 
   - Drag `Date` from `Dim_Calendar` and drop it onto the `Date` column in the `Stats`, `Security`, and `Warnings` tables.
   - Drag `Hour Value` from `Dim_Time` and drop it onto the exact `Hour` integer column you extracted in Power Query for `Stats`, `Security`, and `Warnings`.
4. Ensure all relationship lines show a **"1"** on the Dimension side and a **"*"** (Many) on the Fact tab side.

## Phase 4: Visualization Setup
Go to the **Report View** tab. Switch to dark mode via **View -> Themes**. Create the explicit DAX measures listed in the Formulas guide.

### Page 1: Executive Command Center
1. **Slicers:** Add two Slicer visuals at the top left. Drag `Date String` (from Calendar) into one, and `Hour String` (from Time) into the other. Set both style formats to "Dropdown".
2. **KPI Cards:** Add Card visuals along the top row. Drag in your measures: `Daily Peak CPU`, `Avg Memory Load`, and `Warnings Mitigated`.
3. **The Performance Pulse (Area Chart):** 
   - X-Axis: `Hour String`
   - Y-Axis: `Avg CPU Load`, `Avg Memory Load`
   - *Pro-Tip:* Go to visual settings -> Lines -> set Shape to "Smooth".

### Page 2: Anomalies & Threat Intelligence
1. **The Bot Radar (Scatter Chart):**
   - X-Axis: `Hour String`
   - Y-Axis: `Peak Hourly Connections`
   - Values/Details: `source_ip` from Security.
2. **User Activity Index (Line Chart):**
   - X-Axis: `Hour String`
   - Y-Axis: `Peak Active Processes`
   - Legend: `username`

### Page 3: Diagnostic Root-Cause Analysis
1. **Header Cards:** Add small KPIs at the top reading `Total Warning Events`. 
2. **The Swap Flush (Line Chart):** 
   - X-Axis: `Hour String`
   - Y-Axis: `Avg Swap Usage`
3. **Event Log (Table Visual):** 
   - Drag `Date`, `Hour String`, `message`, and `warning_detail` directly into a Table Visual spanning the bottom of the page.

### The Final Step: Drill-Through Magic
1. Go back to Page 3. In the "Visualizations" pane under "Drill-through", drag the `Hour String` field into the "Add drill-through fields here" bucket. 
2. Now, go to Page 1 or 2. Right-click any spike on a graph (like the 18:00 anomaly). You will see an option to **"Drill-through -> Page 3"**. Clicking it will magically filter Page 3 to show only the warnings and swap drops that occurred precisely at 18:00!
