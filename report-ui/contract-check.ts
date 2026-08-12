import payload from './report-contract.json'
import type { ReportData } from './src'

// The fixture is emitted by the Python Report interface and checked by its contract test.
const checkedPayload: ReportData = payload
void checkedPayload
