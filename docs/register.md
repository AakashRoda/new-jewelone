# Requirement, decision and test register

Baseline: `docs/spec/store-app-build-spec-v0.1.md` (version 0.1, 12 November 2026). Last updated at the end of stage B1, 12 November 2026.

Status words used here:

- **Built**: persistent data, a working screen, server permission checks, history and tests exist.
- **Partly built**: the part that belongs to the stages delivered so far is built; the rest is named.
- **Not started**: belongs to a later stage.
- **Held**: unavailable until the owner decides the linked open decision.

## Confirmed requirements

| Ref | Requirement | Status | Notes |
| - | - | - | - |
| C01 | Masters and stock identity | Partly built | Masters built. Stock item identities, tags and labels are stage B2. No old-tag import exists. |
| C02 | Physical receipt and book records | Built | Inward (physical) and supplier invoice (book) are separate, linked records. Locks built; the first-lot lock is ready and is triggered by stage B2. Mixed inwards held (O01). |
| C03 | Lots and partial tagging | Not started | Stage B2. |
| C04 | Approval stock and supplier returns | Partly built | Approval receipts built for tagged and weight-only stock. Returns and memos are stage B3. |
| C05 | Tagging and studded components | Not started | Stage B2. The 1 ct = 0.200 g conversion is in place and tested. |
| C06 | Piece values and charges | Partly built | Charge-name masters only. No purchase metal rate or metal cost field exists anywhere, and a test guards that. |
| C07 | Untaggable stock and boxes | Partly built | Weight-only receipt into a weight balance built. Box verification is stage B3. |
| C08 | Custody and stock discrepancies | Not started | Stage B4. Receipts record a location and an optional custodian. |
| C09 | Reservations and sales interfaces | Not started | Stage B5. |
| C10 | Sales returns and repair boundary | Not started | Stage B5. |
| C11 | Corrections and permissions | Partly built | Locks, mandatory edit reason and permission-based rights built. No unlock, no administrator rewrite. Correction drafts not built; posting held (O01). |

## Open decisions

| Ref | Decision needed | What the app does meanwhile |
| - | - | - |
| O01 | Corrections to locked inwards; mixed taggable and weight-only receipts | Locked inwards are read-only with an explanation. No correction posting. One stock type per inward. |
| O02 | Weight tolerances (10 to 20 mg per item, 100 mg per box) and how they apply | Two named demo settings are shown on the Masters and settings screen. Nothing posts using them. |
| O03 | Components and charge entry: units, bases, rounding, defaults | Charge masters hold names only. No price formula. |
| O04 | Tag fields, classifications, tag layout and numbering | Metal, purity, item and variety are independent masters. No tags yet. |
| O05 | Untaggable containers: stored tare, box identifiers, multiple boxes | Weight balance per item, purity and location. No boxes. |
| O06 | Custody and closing: locations, handover, cover, loss posting | Demo locations. A receipt records where it was received and, optionally, in whose custody. |
| O07 | Returns of already-tagged supplier items | Not built. |
| O08 | Lot split, merge and reclassification | Not built. |
| O09 | POS and online policies | Not built. |
| O10 | Repair and sales-return exceptions | Not built. |
| O11 | Purchase and karigar details: matching, settlement, document timing | Invoices are simple book records linked to receipts. No settlement, no GST treatment, no invoice editing. |
| O12 | Production operation: deployment, backup, offline, devices, exact permission grants | Local demo only. Demo roles. A dump-and-reload check exists but is not a backup procedure. |

### Decisions that would unblock the most, in order

1. **O01, mixed receipts**: may one inward hold both tagged pieces and weight-only stock, and if so when does it lock?
2. **O02, lot tolerance**: the exact mg-per-item value and whether it is summed across the lot. Needed to finish lot completion in stage B2/B3.
3. **O04, tag numbering and label layout**: needed before real tags are printed in stage B2 (a labelled demo layout can be used until then).
4. **O01, correction notes**: which fields may be corrected after the lock and how. Until then a wrongly confirmed weight-only receipt cannot be fixed in the app.
5. **O12, permission grants**: who really holds `parcel.open`, `inward.edit` and the rest.

## Acceptance tests (feature-to-test checklist)

| Test | Stage | Status | Where |
| - | - | - | - |
| T01 Receipt once; invoice adds nothing; repeat matching | B1 | **Passing** | `tests/acceptance/test_t01_receipt_and_invoice.py` |
| T02 200 g chains, two lots, damaged 15 g piece | B2/B3 | Not started | Receipt fixture exists (`t02_chain_receipt`) |
| T03 Partial tagging, pause and resume | B2 | Not started | |
| T04 Ring with diamonds and coloured stone | B2 | Not started | Carat conversion tested |
| T05 Difference completion at 20 mg and 10 mg (conditional) | B2 | Not started | |
| T06 Difference cannot clear real pieces | B2 | Not started | |
| T07 Approval: 4 retained, 6 returned, actual weights | B3 | Not started | Receipt fixture exists (`t07_approval_pieces`) |
| T08 Gold balls: receive 100 g, return 50 g, match invoice | B1 + B3 | **Direct-weight parts passing** | `tests/acceptance/test_t08_direct_weight_receipt.py`. The 50 g return is stage B3. |
| T09 Box tare and discrepancy | B3 | Not started | |
| T10 Edits before and after lock; direct-weight lock | B1 + B2 | **B1 parts passing** | `tests/acceptance/test_t10_inward_locks.py`. The lock that the first lot applies is built and tested; creating a lot from a screen is stage B2. |
| T11 Label reprint, printer failure | B2 | Not started | |
| T12 Issue 200 bangles, verify 198 (conditional) | B4 | Not started | |
| T13 One missing, one unexpected | B4 | Not started | |
| T14 Wrong tag sold | B4 | Not started | |
| T15 Approval by permission, not title | B4 | Not started | Permission-not-title is already how every built action works. |
| T16 Estimate and layaways | B5 | Not started | |
| T17 Layaway conversion once | B5 | Not started | |
| T18 Online and in-store race | B5 | Not started | |
| T19 Sales returns and repair release | B5 | Not started | |
| T20 Piece values and charges; no purchase metal rate | B2 | Not started | "No purchase metal rate field" guard already passing. |
| T21 New taggable and untaggable stock; no old-tag import | B1 + B2 | **B1 parts passing** | `tests/acceptance/test_t21_new_stock_only.py`. New tags are stage B2. |
| T22 Retries and races | B3 | **B1 share passing** | `tests/test_once_only_and_concurrency.py` covers receipts and invoice links. Tag and return races come with those features. |
| T23 Locked inward while correction policy is unresolved | later | Covered in effect | Locked edits are refused for every user, including one with all permissions and a Django superuser. No correction draft screen yet. |
| T24 Prepare then dispatch a supplier return | B3 | Not started | |

Passing tests establish implemented behaviour. They are not hardware acceptance and not statutory invoice compliance.

## Build stages

| Stage | Status |
| - | - |
| B0 Repository and decisions | Done |
| B1 Receipt foundation | Done |
| B2 Lots and piece tagging | Next |
| B3 Supplier returns and verification | Not started |
| B4 Custody and exceptions | Not started |
| B5 Sales interfaces | Not started |
| B6 Decision completion and production readiness | Not started |
