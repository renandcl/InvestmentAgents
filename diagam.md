# Investment Manager - Architecture Diagram

## Simple Overview
```mermaid
flowchart LR
 subgraph subGraph0["Data Analysis"]
    direction TB
        AC["Analysts Coordinator"]
        MA["Market Analyst"]
        NA["News Analyst"]
        FA["Fundamentals Analyst"]
        SA["Social Media Analyst"]
  end
 subgraph subGraph1["Researchers Discussion"]
        BR["Bull Reseacher"]
        BER["Bear Researcher"]
        RM["Research Manager"]
  end
 subgraph subGraph2["Investment Plan Decision"]
        TR["Trader"]
  end
 subgraph subGraph3["Risk Discussion"]
        AD["Aggressive Debator"]
        CD["Conservative Debator"]
        ND["Neutral Debator"]
        RMG["Risk Manager"]
  end
    Init(["Ticker"]) -- Start Analysis --> IM["Investment Manager"]
    IM <-- Phase 1 --> AC
    AC <--> MA & NA & FA & SA
    IM <-- Phase 2 --> RM
    RM <--> BR & BER
    IM <-- Phase 3 --> TR
    IM <-- Phase 4 --> RMG
    RMG <--> AD & CD & ND
    MA -. Market Report .- State["Document"]
    NA -. News Report .- State
    FA -. Fundamentals Report .- State
    SA -. Social Media Report .- State
    RM -. Investment Plan .- State
    TR -. Investment Plan Report .- State
    IM -. Final Trade Decision .- State
    State@{ shape: db}
    Memory["Past Memory"]
    Memory@{ shape: db}
    Memory -.- subGraph1 & subGraph2 & subGraph3
```
