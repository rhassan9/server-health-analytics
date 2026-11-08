# Server Health Dashboard - DAX Reference

These are the exact Data Analysis Expressions (DAX) formulas you will need to build the "Project Sentinel" architecture cleanly. Do not rely on Power BI's automatic sum/average features; creating explicit measures below ensures your visuals never break when leadership clicks on slicers.

## 1. Dimensional Modeling (Calculated Tables)

To allow the dashboard to cross-filter the exact hour when the anomaly occurred across all three logs (Stats, Security, Warnings), you must generate separate Date and Time dimension tables. Go to the **Modeling** ribbon -> **New Table**.

### The Calendar Dimension
This guarantees you have every single consecutive date, even on days your server doesn't log anomalies. Essential for the Snowflake future-proofing slice.
```dax
Dim_Calendar = 
ADDCOLUMNS(
    CALENDARAUTO(),
    "Year", YEAR([Date]),
    "Month Name", FORMAT([Date], "MMM"),
    "Month Number", MONTH([Date]),
    "Day of Week", FORMAT([Date], "ddd"),
    "Date String", FORMAT([Date], "yyyy-mm-dd")
)
```

### The Hour Dimension
This translates your raw 0-23 hours into a clean dimension for charts.
```dax
Dim_Time = 
GENERATE(
    GENERATESERIES(0, 23, 1),
    VAR _Hour = [Value]
    RETURN ROW(
        "Hour Value", _Hour,
        "Hour String", FORMAT(_Hour, "00") & ":00"
    )
)
```

---

## 2. Core Dashboard Measures

Go to the **Modeling** ribbon -> **New Measure** and paste these in.

### 📈 System Load KPIs (From the `Stats` Table)
```dax
Avg CPU Load = AVERAGE(Stats[cpu_pct])
```
```dax
Daily Peak CPU = MAXX(KEEPFILTERS(VALUES('Dim_Calendar'[Date])), CALCULATE(MAX(Stats[cpu_pct])))
```
```dax
Avg Memory Load = AVERAGE(Stats[memory_pct])
```
```dax
Avg Swap Usage = AVERAGE(Stats[swap_pct])
```

### 🛡️ Security & Traffic KPIs (From the `Security` Table)
```dax
Peak Hourly Connections = MAX(Security[connection_count])
```
```dax
Peak Active Processes = MAX(Security[active_processes])
```
```dax
Unique IPs Monitored = DISTINCTCOUNT(Security[source_ip])
```

### ⚠️ Anomaly Detection KPIs (From the `Warnings` Table)
```dax
Total Warning Events = COUNTROWS(Warnings)
```
```dax
Warnings Mitigated = 
IF(
    ISBLANK([Total Warning Events]), 
    "0 (System Healthy)", 
    [Total Warning Events]
)
```
