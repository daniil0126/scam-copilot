import {
    CellStyleModule,
    ClientSideRowModelApiModule,
    ClientSideRowModelModule,
    CsvExportModule,
    EventApiModule,
    NumberFilterModule,
    QuickFilterModule,
    RenderApiModule,
    RowApiModule,
    RowStyleModule,
    TextFilterModule,
    TooltipModule,
    ModuleRegistry,
} from "ag-grid-community"

// AG Grid Community only. Registered once for the whole app; only the modules the tables use, to keep the bundle small.
let done = false
export function setupGrid() {
    if (done) return
    done = true
    ModuleRegistry.registerModules([
        ClientSideRowModelModule,
        ClientSideRowModelApiModule,
        RowApiModule,
        EventApiModule,
        RenderApiModule,
        CellStyleModule,
        RowStyleModule,
        TextFilterModule,
        NumberFilterModule,
        QuickFilterModule,
        CsvExportModule,
        TooltipModule,
    ])
}
