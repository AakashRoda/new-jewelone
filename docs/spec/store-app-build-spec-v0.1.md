Build a working jewellery store application for the owner’s independent AI-assisted development effort, alongside the consultancy’s implementation. Start with inventory and the interfaces already defined for purchases, sales, reservations, repairs, and RFID. Deliver persistent, testable workflows that can be demonstrated with the examples below.

**Version 0.1 · 12 November 2026 · Implementation draft.** No application code has been built by creating this specification. The business baseline is [Store App Spec Draft](https://chatgpt.com/space/page_b1f92b4375948191afa2c8ba9633f001), reviewed at revision 17. This is a separate implementation specification; it does not replace or modify the consultancy draft.

# Instructions for the coding agent

Read this specification before changing code. If a repository is supplied, inspect its instructions, existing architecture, migrations, and tests before selecting a stack or replacing working code. If there is no repository, establish a small runnable project and record the stack choice as an engineering decision. The owner has not selected a framework, database product, deployment platform, offline strategy, or hardware vendor in this specification.

Use these statuses consistently:

| Status | Meaning | Agent action |
| - | - | - |
| Confirmed | The owner has described or accepted the business behaviour. | Implement it and preserve its meaning. |
| Engineering guidance | A suggested way to make confirmed behaviour reliable. | Adapt to the repository and record meaningful technical deviations. |
| Open decision | Business behaviour is not yet agreed. | Keep it explicit; ask when it blocks the current feature. Do not silently choose a destructive or financial outcome. |
| Deferred module | The module is in scope but its detailed workflow is still to come. | Provide narrow integration boundaries when needed; do not invent the whole module. |

Build in small working increments. For each increment, supply migrations, backend behaviour, usable screens, relevant automated checks, demo data, and a brief account of what works and what is still blocked. A set of screens backed only by temporary browser state is not completion of an inventory workflow.

Do not wait for every open decision before building confirmed flows. Use named demo settings for unresolved numerical values, clearly separated from production configuration. For unresolved stock mutations such as post-lock corrections or lot merges, build the review interface if useful, but leave posting unavailable until the relevant policy is agreed.

Use this conversation’s requirements as the baseline. Do not automatically import features from older jewellery ERP discussions. Keep business questions separate from routine technical choices. Never turn an engineering suggestion into a claim that the owner confirmed a business rule.

# Product scope

Inventory is the first detailed implementation area. The following 21 modules are required; the build sequence later in this document is an engineering proposal, not an agreed consultancy delivery schedule.

| No. | Module | Current detail status |
| - | - | - |
| 1 | Inventory management | First build area; confirmed workflows and open decisions below |
| 2 | Customer relations management | Required; detail pending |
| 3 | POS | Layaway conversion, estimates, and condition-based sales returns defined; remaining detail pending |
| 4 | Purchase | Physical/book separation and invoice links defined; remaining detail pending |
| 5 | Gold Saving Schemes | Required; detail pending |
| 6 | Analytics and Reports | Required; detail pending |
| 7 | GST Filing | Required; detail pending |
| 8 | Audit Trail | Mandatory inward-edit reasons and preservation of returned-item history defined; remaining detail pending |
| 9 | User Roles based access | Employee permissions, parcel opening, and inward-edit restrictions identified; full permission matrix pending |
| 10 | Karigar Management | Required; karigar inwards identified |
| 11 | Approvals | Receipt, selection and supplier return memos defined; remaining detail pending |
| 12 | WhatsApp Chatbot Integration | Required; detail pending |
| 13 | SMS Integration | Required; detail pending |
| 14 | E-commerce Integration | Online checkout stock commitment and prevention of duplicate sale defined; remaining detail pending |
| 15 | E-commerce app | Required; detail pending |
| 16 | In-store Mobile App | Required; detail pending |
| 17 | Owner’s Dashboard | Required; detail pending |
| 18 | RFID Support | Critical requirement; daily issue and closing use case captured; hardware and remaining detail deferred |
| 19 | Loyalty Points | Required; detail pending |
| 20 | Gift Cards | Required; detail pending |
| 21 | Repair | Separate module confirmed; detailed workflow deferred until the Repair module is specified |

Repair remains a separate module. E-commerce Integration, E-commerce app, In-store Mobile App, and Owner’s Dashboard remain distinct modules. Do not merge them or add unrelated modules without a new requirement.

# Confirmed business requirements

## C01 Masters and stock identity

Maintain metal, purity, item, variety, unit, making-charge rules, custom other-charge definitions, and the HSN references required by the wider application. The exact metal/category/purity relationship and final validation rules remain open. Examples include Gold, Gold 22K, Chain, Ring, Machine Chain, and Hollow Chain. Weights may be in grams or carats; counted units use Nos.

Taggable stock has individual stock identities. Untaggable stock is tracked by weight without individual pieces or mandatory piece counts. Every physical quantity must retain its source and its location or custody information. A lot groups stock from an inward for selection and tagging; it is not a supplier invoice and is not an additional physical receipt.

A printed label and a physical RFID identifier are representations associated with the stock item. Reprinting a label must retain the same item identity and history. All new stock is entered into this software. Old tags are not imported; new tags are created through this application’s tagging workflow.

## C02 Physical receipt and book records

Physical stock and invoice-based book stock are separate, linked records. An inward records actual goods received. A supplier purchase invoice records the supplier’s stated quantities and values; entering or matching it must never add the goods physically a second time.

Sources include supplier purchases, supplier approval memos, and karigar inwards. Only an authorised person may open a supplier parcel and verify its contents. Record source-declared weight, actual received weight, their difference, supplier/source references, receiving user, and relevant location or custody. Record the entire quantity physically received, including damaged pieces and designs later rejected.

Taggable stock proceeds from inward to one or more relevant lots. Untaggable stock adds the received weight directly to the item balance when its receipt is confirmed. Do not require a supplier invoice before physical receipt, lot creation, or tagging.

For taggable stock, the inward becomes locked as soon as its first linked lot is created, even before any tag exists. For untaggable stock, it locks when the receipt is confirmed and added to stock. Before the applicable lock, editing requires inward-entry permission and a clear reason. After the lock, direct editing is prohibited; a separate correction process is required. The detailed behaviour of mixed taggable and untaggable inwards is open.

## C03 Lots and partial tagging

A lot carries its original piece count, gross weight, net weight, classification, supplier/source links, and its remaining untagged balances. Show original, tagged, returned, remaining, and explicitly recorded difference values without losing the original receipt.

The tagging screen must let the operator save one piece at a time, pause, and resume the same lot. A partially processed lot stays active and appears in untagged stock for its item type. Example: 10 chains weigh 100 g gross and net; tagging one 10 g chain leaves 9 pieces and 90 g gross and net.

Damaged pieces remain untagged inside the created lot while other pieces are tagged. Applying the latest clarification to the chain receipt: inward 200 g, create a 100 g machine-chain lot and a 100 g hollow-chain lot; the hollow-chain lot contains 85 g suitable for tagging and one damaged 15 g chain. Do not create an 85 g hollow-chain lot that omits the damaged piece.

Complete a lot when all original pieces and weights are accounted for through tagging, recorded supplier returns, and any explicitly permitted weighing difference. Closing a lot does not remove retained tagged items from inventory. A later sale of a tagged piece must not increase the lot’s untagged balance.

A weighing tolerance of 10–20 mg per item has been accepted in principle; the exact setting and its application to gross/net and mixed tagged/returned lots are open. With an explicit 20 mg demo setting, 10 chains totalling 99.800 g from a 100.000 g lot leave 0 pieces and 0.200 g awaiting reconciliation. The operator explicitly records that difference and completes the lot. Do not invent a residual item or silently change tag weights. A difference cannot dispose of real untagged pieces. The aggregate-per-lot tolerance formula is engineering guidance pending business confirmation.

## C04 Approval stock and supplier returns

For taggable approval stock, inward the full received count and weight, then create the lot. Example: receive 10 items totalling 100 g; retain and tag four, and send the remaining six back through an approval return with a supplier return memo. Use actual weights; four items need not weigh 40 g. The six untagged items do not need individual tags just to be returned.

A supplier return memo is required for damaged items and rejected designs sent back to the supplier. Link the return to its supplier, original inward, source approval memo where applicable, and lot where applicable. Record actual returned weight and piece count for taggable stock. The approval return and its supplier return memo describe the same outward movement and must not deduct stock twice.

Setting items aside or drafting a memo does not remove them from physical stock. Dispatching the return reduces physical stock and the outstanding untagged lot balance. Preserve original inward and lot totals. Returning goods is an outward movement, not a weighing loss or an edit to the original inward.

The retained four items stay in stock and retain their histories after lot completion. The later supplier invoice is matched separately, without another receipt. A lot can be complete while invoice matching remains pending. Supplier acknowledgement and financial settlement do not replace physical dispatch records.

Untaggable approval stock follows the same physical principle without lots: receive 100 g of gold balls directly into stock; dispatch 50 g on an approval return with a supplier return memo; 50 g remains, assuming no other movements. Preserve the original 100 g inward and separate 50 g return. Returns of already-tagged stock need a further business decision.

## C05 Tagging and studded components

Selecting a lot shows its classification and supplier/purity defaults. In the single-item example, category is 22K Ornaments, item is Ring, and variety is selected during tagging. Supplier and purity populate from the lot. With one item remaining at 5 g gross and 4 g net, the weights can populate directly. For multi-piece lots, capture each item’s own measured weights and display the remaining lot totals alongside them.

The Other charges checkbox opens studded-material details. Gross minus net gives 1 g of other weight in the ring example:

| Component | Entered weight | Gram equivalent | Pieces and details |
| - | -: | -: | - |
| Diamonds | 1 ct total | 0.200 g | 100 diamonds, VVS clarity, E–F colour |
| Coloured stone | 4 ct total | 0.800 g | Count not specified |
| Net metal | 4.000 g | 4.000 g | Ring metal |
| Gross item | | 5.000 g | One ring |

The 1 ct diamond weight is the total across 100 stones, not the weight of each stone. Do not deduct component weight again after net metal weight is entered. Support component detail records without confusing their stone counts with the count of jewellery pieces. Component mismatch tolerance and whether a mismatch prevents saving remain open and are separate from lot-tagging tolerance.

## C06 Piece values and charges

Attach diamond, gemstone, and CZ purchase and sale values separately to the individual piece and its components. Attach supplier wastage, making charges paid to the supplier, making charges chargeable to the customer, and user-created other charges to that piece. Keep HUID details separate from any associated HUID charge. A custom charge is created by the software user/business, not an instruction for a retail shopper to create a charge.

Supplier wastage and customer making percentages have different meanings. Supplier wastage adds percentage points to the charging purity: 91.6 + 4 = 95.6. The separate customer percentage example is 91.6 × 1.04 = 95.264. Do not use one ambiguous percentage field or treat the charging factor as physical purity.

Purchase metal-rate tracking and historical metal purchase-cost valuation are excluded from scope. Do not require a purchase metal rate for receipt, tagging, stock availability, or sale; do not create per-piece metal acquisition costs or metal-cost-based margins. Supplier invoice stated values remain separate book/document values. The earlier supplier rupee examples explain consolidation and do not override this exclusion.

Exact price-entry units, rates versus totals, charge bases, rounding, default application, and later changes are open. Customer sale metal-rate calculations belong in POS. Charge handling for pooled untaggable stock remains open without introducing piece tags.

## C07 Untaggable stock and boxes

Untaggable stock, such as gold balls, enters the relevant item’s weight balance directly from the inward. No lot, individual item record, or piece count is required. A sale and physical issue of 1 g reduces the expected contents by 1 g.

Closing verification measures the whole box, subtracts its empty-box tare, and compares the contents with the system’s expected physical stock. Tare is packaging, never gold stock. Contents weight is the item weight at its recorded purity, not fine-gold equivalent weight.

Example: empty box 50.000 g, opening contents 20.000 g, sale and issue 1.000 g, closing gross 69.000 g. Actual and expected contents both equal 19.000 g. If closing gross is 68.900 g, actual contents are 18.900 g and the signed discrepancy is −0.100 g. Preserve the discrepancy; never overwrite the ledger merely because a weighing was entered.

The owner suggested 100 mg per box as a possible tolerance; it remains tentative. App-stored tare, box identifiers, multiple boxes, and transfers between them are proposed rather than confirmed. The core box calculation can be implemented with explicit tare input while those choices remain open.

## C08 Custody and stock discrepancies

Support the morning issue and evening return use case: 200 distinct RFID-labelled bangles go to Employee A; two identified pieces are sold and delivered; the correct remaining 198 are verified back into the safe. Match identities, not merely a count of 198.

Responsibility for missing pieces rests with the person who had possession. Retain custody and handover evidence to identify that person. A missed read is an exception to investigate, not proof of physical loss. Unreadable labels must be reprinted for the identified existing piece.

An unexpected piece may result from a wrong tag being selected during sale. If A is recorded as sold but B was actually delivered, A appears unexpectedly present and B appears missing. Investigate the linked discrepancy; do not automatically net the two counts, add a new piece, or post a loss. Detailed sale correction belongs to POS.

Any user with the permission for the specific correction or loss task may approve it. Do not hard-code the owner or a manager title as the only approver. Keep the responsible custodian and approving user distinct.

Counter-and-custodian tracking, acknowledged handovers, optional home tray references, cashier transfers, and temporary cover are proposed controls. The owner’s use case includes presenting items on a cloth; live tray tracking must not be imposed as a prerequisite. The final location list, precise transfer acceptance rules, closing with unresolved exceptions, and loss-posting process remain open.

## C09 Reservations and sales interfaces

An estimate does not hold stock. A layaway reserves specified items and may have payment records, including advances; an advance does not itself complete the purchase. A layaway can exist without an advance. The sales invoice screen provides a layaway list and converts an entry to an invoice when the purchase is completed.

A committed online checkout marks the piece Sold awaiting dispatch and prevents an unrelated second invoice. Allow the invoice belonging to the existing order. Commitment changes availability; it does not remove the piece from physical custody before dispatch or handover.

The exact online commitment event, failed/pending payments, expiry, cancellation, partial conversion, refund rules, sale rate fixing, and full invoice calculations are deferred to POS and E-commerce. Implement inventory commitments and their contract tests without inventing those policies or integrating a live payment gateway.

## C10 Sales returns and repair boundary

A piece actually sold and returned must re-enter through a sales return linked to its original sale and original stock identity. Undamaged original-condition items return to saleable stock. Accepted minor-damage items enter Needs repair: physically accounted for but unavailable for sale. After repair, release the same item to saleable status without a second physical addition.

Preserve inward, lot, tag, sale, return, and subsequent history. Printing another label does not reactivate a sold item. The detailed Repair module is deferred: jobs, external karigar handling, measurements, completion checks, and release roles must be worked out there. Damage beyond the accepted minor-damage case and financial refunds remain open.

An erroneous sold flag caused by selection of the wrong tag is a sale-correction case, not a reason to fabricate a customer return for an item that never left.

## C11 Corrections and permissions

Implement the confirmed inward locks and mandatory pre-lock edit reason. Correction and loss approval authority is permission based. A user’s relevant rights, rather than being the original creator, determine whether an allowed action may be performed.

The proposed Inward correction note has not been approved as the final posting workflow. Its intended direction is a separate note retaining old values, revised values, reason, actor, approval, and affected stock links. A preview would show effects on lots, tags, returns, sales, and invoices. An entry mistake must remain distinct from a real stock shortage.

Do not implement an unrestricted unlock button, silent administrator rewrite, automatic loss write-off, or full-receipt reversal that leaves dependent tags and movements inconsistent. Read-only history and correction drafts may be built; enable posting only after the policy in O01 is resolved.

# Engineering design

The following is implementation guidance for the independent build. It does not settle the open business policies. Prefer one application backend with a transactional relational data store and clear domain services; avoid introducing distributed services solely for the inventory module. Adapt this design to an existing repository where appropriate.

## Data records and relationships

Use stable internal IDs independently of printed codes, document numbers, or RFID hardware IDs. Suggested logical records are below; physical table names may follow the repository’s conventions.

| Record | Essential fields and relationships |
| - | - |
| Master records | Metal, purity, item, variety, unit, charge definition, supplier, location, user, role and permission. Keep changes traceable where historical use would be affected. |
| Inward and inward line | Source type/reference, supplier or karigar, stock mode, classification, declared and measured weights, count when applicable, discrepancy, receipt confirmation, lock state and cause, receiving actor and location/custody. |
| Lot | Original inward-line allocation, supplier and classification defaults, original gross/net/count, processing state, tagged allocations, returns and recorded differences. An inward may feed multiple lots; prevent overlapping allocation. |
| Stock item | Original inward and lot, stable identity, printed tag code, classification, gross/net/other weight, HUID where applicable, condition, commitment, location/custody, and history links. |
| Component and piece charge | Parent item, material/quality details, total component weight and unit, stone count where known, separate buy/sell values, charge definition, supplier/customer applicability and calculation basis where agreed. No metal purchase-rate field is required. |
| Untaggable balance and movements | Item/classification and applicable physical bucket, source inward, signed weight movements, locations/custody and source transaction. The balance is a projection of movements, not an editable total. Box-level allocation remains conditional on O05. |
| Supplier return and lines | Supplier, source inward/approval, lot where applicable, actual weights/counts, memo reference, preparation and dispatch state, dispatch actor. One outward event even when linked to an approval return. |
| Invoice reference and matching | Supplier document identity, stated quantities/values, links to existing receipts and retained items/weights. No independent physical receipt effect. Full purchase accounting is deferred. |
| Movement and custody handover | Stock IDs or direct-weight quantities, movement kind, from/to location and custodian, source command/document, recorded time, actor, acknowledgement if used. |
| Commitment | Stock identity, layaway/order/sale reference, commitment kind and lifecycle. Prevent competing active commitments to the same piece. |
| Sales return reference | Original sale and item, actual receipt event, condition and inventory outcome. It restores the same identity. |
| Verification session and observations | Expected snapshot, observed unique IDs or measured gross/tare, cutoff information, manual verification, missing/unexpected results and resolution links. |
| Approval and audit event | Task type, target record, requester/actor, approver where applicable, permission checked, reason, before/after or event payload, timestamp, outcome. |
| Print job and RFID mapping | Item ID, label version/job result; separate hardware ID mapping with history if RFID hardware replacement is later approved. |

Do not represent all of location, ownership, condition, processing, reservation and document status with one StockStatus field. A reserved item can still be in the safe; an item needing repair can still be physically held; a completed lot can still await its invoice.

## Quantity effects

Keep store-wide physical totals distinct from the allocation of that stock to inward balances, lots, tags, locations, and custodians.

| Action | Store physical stock effect | Other effect |
| - | - | - |
| Confirm physical inward | Add the actual received quantity once | Create source history; direct-weight stock locks here |
| Create a lot | None | Allocate from receipt; apply taggable inward lock |
| Create an item tag | None | Allocate from untagged lot balance to an identified item |
| Record or match purchase invoice | None | Update separate book/document links |
| Create estimate | None | No reservation |
| Create layaway or committed online order | None | Change availability and link the commitment |
| Transfer within the store | None | Move location/custody once |
| Deliver an item or issue a weight sale | Subtract once when it physically leaves | Preserve the sale and item/source links |
| Dispatch supplier return | Subtract once | Clear relevant untagged lot balance or direct-weight balance |
| Receive a genuine sales return | Add once | Restore original identity and condition-dependent availability |
| Reprint label | None | New print job for the same identity |
| Mark repair complete for an item already held | None | Change condition/availability through the Repair interface |
| Record permitted lot weighing difference | Explicit measured-quantity reconciliation only | Remove no fictitious piece; preserve original receipt and difference |
| Post a correction or loss | Depends on policy still to be defined | Approval alone must not silently mutate balances |

A recorded weighing difference is visible reconciliation of measured quantities, not a supplier return or physical dispatch. Its financial treatment remains open. Keep it separate in both reporting and any movement representation.

## Invariants and numeric handling

Enforce these in domain services and database transactions, not only in screens:

1. A receipt, dispatch, return, or quantity adjustment is applied once, even after retry or double-click. Lot creation and tagging cannot duplicate physical stock.

2. For each count-bearing lot, original pieces equal tagged allocations plus dispatched untagged returns plus remaining untagged pieces. There is no piece count for a weight-only difference.

3. For each tracked lot weight, original weight equals tagged allocations plus dispatched untagged returns plus remaining untagged weight plus signed recorded difference. Until the policy is confirmed, do not allow negative balances or automatically accept overweight results.

4. Saving a tag and reducing the remaining lot allocation is one transaction. Two operators cannot tag the same remaining quantity twice. The same applies to competing tag and supplier-return actions.

5. Lot progress tracks allocations, not the current saleable count of its tagged items. A sale or a later genuine sales return does not reopen original untagged allocations.

6. A piece has at most one conflicting sales commitment at a time. Layaway conversion preserves the commitment without an intervening window of availability.

7. A confirmed inward cannot be directly edited once its applicable lock has occurred. Recheck the lock on save to prevent a concurrent lot creation from bypassing it.

8. Reprints, book invoice matching, and status-only repair release have no physical quantity effect. Genuine sales returns retain original identity.

9. Scan duplicates are not additional pieces. Unknown or unexpected IDs are exceptions, not instructions to create stock.

10. Every mutation identifies the actor and source transaction. A correction or loss approval checks the current configured permission.

Use exact decimal arithmetic for weights, carats, percentages, and money. Maintain enough internal precision to represent 10 mg and the 1 ct = 0.200 g conversion without binary floating-point drift. Keep unit conversions explicit and round only at agreed boundaries. Do not treat an unentered component value or charge as a known zero. Keep quantities, purity percentages, percentage-point wastage, monetary rates, and monetary totals distinct.

## Commands and integration contracts

Expose explicit business commands behind whichever API style the project uses. Give stock-changing requests a retry key and an expected record version or equivalent concurrency guard. A repeated retry key with the same payload returns the original result; a different payload must not silently reuse the key.

| Command or interface | Main inputs | Required checks or result |
| - | - | - |
| ConfirmInward | Source, lines, actual weights/counts, location/custodian | Permission; once-only receipt; direct-weight lock |
| EditInward | Target, changes, reason, expected version | Inward-entry permission; lock rechecked at commit |
| CreateLot | Inward line, classification and quantity allocation | Available unallocated receipt; lock inward atomically |
| CreateTag | Lot, piece measurements, variety, components and charges | Available count/weight; atomic tag allocation; no physical addition |
| DispatchSupplierReturn | Return memo and source allocations | Actual dispatch; available quantity; one deduction |
| RecordDifferenceAndCompleteLot | Lot, explicit difference, tolerance policy | No unresolved physical pieces; permitted policy; no silent write-off |
| MatchPurchaseInvoice | Document values and existing stock references | No stock addition or metal purchase-rate requirement |
| ReservePiece and CommitOnlineOrder | Item IDs and owning layaway/order | Eligibility and competing commitments checked atomically |
| ConvertLayaway | Layaway and linked sale | One conversion; preserve commitment and payment references |
| DeliverStock | Existing sale/order and physical items/weight | Valid commitment/source; one actual outward movement |
| ReceiveSalesReturn | Original sale/item, received condition/location | Genuine received item; same identity; no duplicate restoration |
| RecordVerification | Expected snapshot and observations | Unique item comparison or gross-minus-tare; no automatic adjustment |
| ReprintLabel | Existing item and requested label | No stock/status change; traceable print job |
| RepairCompleted | Existing item and trusted repair reference | Status-only release when item is already physically held; detailed policy deferred |

Keep printer, scale, RFID reader, e-commerce event, and repair integrations behind adapters. Start with explicit manual entry and simulated device events for testing. A simulator is not evidence that real hardware works. Do not attach a live online event to the commitment command until the event’s business meaning is decided.

## Permissions and audit

Use configurable capabilities rather than special treatment of job titles. Illustrative keys include inward.create, inward.edit, parcel.open, lot.create, tag.create, tag.reprint, supplier_return.dispatch, custody.issue, custody.receive, verification.record, correction.approve, and loss.approve. These are implementation names; exact grants and any request/post separation remain open.

Check permissions on the server at action time. Demo roles may exercise allowed and denied paths but must be labelled as demo configuration. Do not grant ordinary inward-entry permission an implicit post-lock override. Permission-based approval is confirmed; a mandatory two-person workflow is not.

Preserve reasons and before/after values for permitted edits, append linked events for receipts and outwards, and keep print and approval history. Avoid direct delete/update operations that destroy used stock identities or source transactions. Exact retention, reversal and deletion policies remain business decisions.

# Screens and operator behaviour

These screens are an implementation proposal for the confirmed flows. Use store-facing names and units; keep internal ledger and database terminology out of normal operator tasks.

| Screen | Required working behaviour |
| - | - |
| Stock overview | Separate tagged, untagged and weight-only stock; show physical presence separately from availability; filter by item, variety, supplier and location where supported. |
| Inward entry and detail | Show actual versus source-declared quantities, source document, condition notes and lock reason; explain why editing is unavailable. |
| Lot creation and work queue | Allocate receipt stock by variety; include damaged/rejected stock in its lot; show active partial lots and retained/returned/difference totals. |
| Tagging | Persistent remaining count/gross/net side panel; per-piece capture; component rows; separate buy/sell values and charges; save one item, print and resume. |
| Stock item detail | Identity, source history, weights/components, applicable charges, HUID, location/custody, condition and commitment; reprint without new stock. |
| Supplier return memo | Select untagged lot quantities or direct weights; preview actual returned quantity; separate preparation from dispatch. Already-tagged returns stay pending policy. |
| Custody issue and receipt | Bulk unique item selection or scans, expected versus observed list, handover history; acceptance rules identified as proposed until confirmed. |
| Closing verification | Show missing and unexpected identities separately, unreadable-tag resolution, or box gross/tare/contents/discrepancy; no silent adjustment. |
| Layaway list and sale integration | Open reserved entries from the sales screen; retain linked payments and item commitment; do not represent an estimate as a hold. |
| Approvals and history | Show task, responsible custodian, proposed change/loss, permission-qualified approver, reason and audit history; gate unresolved posting workflows. |
| Masters and settings | Maintain agreed masters and charge definitions; expose named test tolerances; mark production policies requiring a decision. |

Supply useful validation messages with the conflicting item or quantity. Preserve form input after recoverable errors. Report printer failure separately from successful tag creation so retrying print cannot create another item. Prevent double submission while retaining backend idempotency. Stock history and operator work queues are part of the inventory implementation; the full Analytics and Reports module remains separate.

# Acceptance scenarios

Implement these as repeatable fixtures and tests appropriate to the current increment. Tests marked conditional exercise an explicitly named policy or demo setting; they do not confirm that setting for production. Use synthetic stock and customers.

| Test and requirements | Scenario | Expected result |
| - | - | - |
| T01 C02 | Receive goods, then enter and match their supplier invoice. Repeat matching. | Physical receipt happens once; invoice entry/matching adds no physical stock. |
| T02 C02 C03 C04 | Receive 100 g machine chains and 100 g hollow chains, including a damaged 15 g hollow chain. | Inward 200 g; two 100 g lots. Tag 85 g of suitable hollow chains; 15 g remains in that lot until memo dispatch. No omission or fake weighing loss. |
| T03 C03 | Lot contains 10 chains and 100 g gross/net. Tag one 10 g piece, leave the screen, then resume. | The existing tag remains; 9 pieces and 90 g gross/net remain active and untagged. |
| T04 C05 | Tag the 5 g gross/4 g net ring with 100 diamonds totalling 1 ct and coloured stone totalling 4 ct. | Other weight is 1 g; diamond weight is 0.2 g total; no double deduction or 100-fold multiplication. |
| T05 C03 conditional | All 10 tags total 99.800 g against 100.000 g. Use an explicit aggregate 20 mg-per-item demo policy. Repeat at 10 mg. | At 20 mg, explicit 0.200 g difference completion succeeds and retains history. At 10 mg, normal in-tolerance completion rejects it. |
| T06 C03 | One chain is tagged and nine physical chains remain; attempt difference completion. | The system does not clear real untagged pieces as a weight difference. |
| T07 C04 | Approval inward 10 pieces/100 g. Four retained items actually total 43 g; six returned items total 57 g. | Tag four and dispatch six with a memo. Lot completes at 4 tagged + 6 returned; four items remain held. No assumed 40/60 g split. Invoice may remain pending. |
| T08 C04 C07 | Receive 100 g of untaggable gold balls, dispatch 50 g as an approval return, and later match the retained 50 g invoice. | Current stock from this receipt is 50 g; no lots/tags/counts; invoice adds nothing. |
| T09 C07 | Box tare 50 g, contents 20 g, sale and physical issue 1 g. Weigh 69 g, then demonstrate a 68.9 g measurement. | Contents compute as 19 g, then 18.9 g; the latter shows −0.1 g discrepancy. Measurement never silently changes expected balance. |
| T10 C02 C11 | Attempt authorised edits before and after first lot creation; also confirm a direct-weight receipt. | Pre-lock edits need a reason. First lot locks taggable inward immediately. Direct-weight confirmation locks its inward. No ordinary edit bypass. |
| T11 C01 C08 | Reprint a damaged/unreadable label; simulate printer failure and retry. | Same stock identity and history; stock count and sale status unchanged. A print retry does not create another tag allocation. |
| T12 C08 conditional | Issue 200 distinct bangles to A; deliver two; verify and accept the other 198. | Reconciliation accounts for exact identities and accepted custody events; no missing or unexpected pieces. |
| T13 C08 | Return 197 expected items plus one item expected elsewhere. | Show one missing and one unexpected despite the total count of 198. |
| T14 C08 | Sale references A but B was delivered. A is still physically present. | Show linked possible sale-selection exceptions, without automatic gain/loss, fake return, or cancellation of the original sale. |
| T15 C08 C11 | Test a user with correction/loss permission but no manager title, and another user without that permission. | Authorised approval succeeds; unauthorised approval fails. Keep approver and responsible custodian distinct. Unresolved posting policy still gates balance changes. |
| T16 C09 | Create an estimate, then a layaway with no advance and one with an advance. | Estimate never holds. Both layaways can reserve; an advance alone does not complete a sale or reduce physical stock. |
| T17 C09 | Convert the same layaway twice; use a fixture with a ₹10,000 advance against a ₹50,000 final invoice. | One linked invoice/conversion and one advance application; no temporary availability gap or duplicated payment. Detailed financial calculations remain POS work. |
| T18 C09 | Simultaneously commit one item online and attempt an unrelated in-store sale. | At most one conflicting commitment succeeds. The existing online order may obtain its own invoice; physical stock remains until delivery. |
| T19 C10 | Receive genuine undamaged and accepted minor-damage sales returns, then a repair-completion event. | Restore original identities once. Minor damage is not saleable; repair completion adds no second physical item. |
| T20 C06 | Record applicable diamond/gemstone/CZ buy/sell values, supplier/customer charges, HUID and a custom charge. | Correct piece associations and separate values. No purchase metal rate or historical metal-cost margin is required. |
| T21 C01 | Add new taggable and untaggable stock. | Taggable stock receives new software identities/tags; untaggable stock enters by weight. No old-tag import workflow is introduced. |
| T22 C02 C03 C04 | Retry receipts and returns; race two tags, or a tag and a return, against the same remaining lot balance. | No duplicate physical effects, negative allocation, or over-allocation; successful result and history agree. |
| T23 C11 | Open a locked inward while correction posting policy is unresolved. | Normal editing stays blocked. A proposed correction cannot silently post through an administrator override. |
| T24 C02 C04 | Prepare a supplier return memo without dispatch, then dispatch once and retry. | Goods remain physically held before dispatch; dispatch deducts once and preserves memo/source history. |

Add coverage for new confirmed decisions when they are agreed. Preserve these fixtures as the basis for comparing the owner’s build with the consultancy’s implementation. Passing tests establishes implemented behaviour, not hardware acceptance or statutory invoice compliance.

# Open decisions and build boundaries

Maintain this register as business decisions are made. Do not treat the proposal text in the consultancy draft as confirmation. A decision can be narrowed to the feature being built; work on unrelated confirmed flows can continue.

| Decision | Needs an owner decision | Safe progress before decision |
| - | - | - |
| O01 Locked inward corrections | Confirm correction notes, eligible fields, dependencies, reversal handling, mixed stock-mode receipts, and effects on completed lots or sold items. | Locks, history, impact preview and non-posting drafts. |
| O02 Weight policies | Exact 10–20 mg setting, aggregation method, gross/net application, returned-item allowance, excess/overweight handling, and whether 100 mg per box is final. | Exact arithmetic, visible discrepancies, explicit demo configurations; no silent production write-off. |
| O03 Components and charge entry | Required attributes, pricing units, rates versus totals, calculation bases, rounding, defaults, change permissions and pooled-stock charges. | Component identity/measurements and separate buy/sell fields; no invented price formula. |
| O04 Tag fields and classifications | Final metal/category/purity relationships, mandatory HUID/component fields where applicable, override rights, tag layout and numbering. | Extensible masters, stable IDs, clear source defaults and a labelled demo label layout. |
| O05 Untaggable containers | App-stored tare, box identifiers, multiple-box allocation and weight transfers. | Direct item-weight stock and explicit gross/tare verification. |
| O06 Custody and closing | Actual locations, handover acknowledgement, temporary cover, cashier transfer, cutoff, manual checks, unresolved closing and loss-posting procedure. | Traceable location/custody records, discrepancy views and permission checks; acceptance workflow remains an explicit proposal. |
| O07 Returns after tagging | How to select and return an already-tagged supplier item, handle its active commitments, and retain its history. | Confirmed untagged lot returns and direct-weight returns. |
| O08 Lot changes | Whether existing lots may split/merge, whether classifications can change, and how wrong allocations are corrected. | Original allocation, partial tagging, supplier returns and exact completion. |
| O09 POS and online policies | Hold expiry, cancellation, refunds, partial layaway conversion, rate fixing, exact checkout commitment event, and wrong-tag invoice corrections. | Inventory commitment interface, labelled simulated events, linkage and concurrency tests. |
| O10 Repair and sales return exceptions | Repair jobs/release roles, measurements after repair, damage beyond minor cases and financial refunds. | Confirmed same-identity return and Needs repair boundary; defer full Repair module. |
| O11 Purchase and karigar details | Source matching, supplier settlement, approval-sale document timing and karigar issue/receipt/settlement. | Separate physical/book records and source references; no metal purchase-rate requirement. |
| O12 Production operation | Deployment/backup/restore expectations, network/offline policy, real printer/RFID/scale protocols, device acceptance and exact permission grants. | Local reproducible app, migrations, synthetic fixtures and device adapters. |

Supplier accounting/GST rules and approval-sale document timing are to be validated in their modules. Do not label a prototype’s documents as compliant invoices merely because inventory can be received or sold before purchase invoice entry.

# Build sequence

Use these stages to produce working vertical slices. Do not represent them as promised consultancy milestones. Each stage should end with a runnable demonstration and relevant acceptance results.

| Stage | Deliverable | Evidence to produce |
| - | - | - |
| B0 Repository and decisions | Inspect or create the project; choose and document the stack; establish migrations, test runner and demo environment. Create a requirement/decision register using C, O, and T references. | Clean start instructions, initial migration and a passing smoke check. |
| B1 Receipt foundation | Masters, supplier/source records, permission checks, physical inward, direct-weight entry, book-document references and audit history. | T01, the direct-weight parts of T08, and relevant T10/T21 checks. |
| B2 Lots and piece tagging | Receipt allocation, lock on first lot, partial tagging, component capture, piece values/charges, printing adapter and item history. | T02–T06, T11, T20, T21 and concurrent tag checks. Demo tolerance clearly identified. |
| B3 Supplier returns and verification | Untagged lot returns, approval returns/memos, direct-weight returns, dispatch separation, box calculations and lot completion. | T07–T09, T22 and T24. Reconcile all fixture balances. |
| B4 Custody and exceptions | Configurable locations/custody, simulated unique-ID scans, reconciliation and permission-qualified approval records. | T12–T15 with proposed handover settings clearly documented; no unapproved loss posting. |
| B5 Sales interfaces | Estimate/layaway commitments, linked conversion, simulated online commitment, delivery, same-identity sales return and Repair boundary. | T16–T19 plus concurrency/retry checks. Full POS, payments and repairs remain scoped separately. |
| B6 Decision completion and production readiness | Resolve remaining policies for the intended release; replace adapters with agreed devices; exercise backups/restores and operational failures. | Owner walkthrough, physical hardware checks, permissions review, migration/recovery evidence and remaining limitations. |

At each stage, update a feature-to-test checklist. Do not mark a stage complete just because pages or endpoints exist. If a decision blocks one action, identify the exact action and O reference and finish the independent work.

# Definition of done

An implemented feature has persistent data, a working operator flow, backend permission checks, its required audit/source history, and tests for its quantity effects. Relevant retry and concurrent-update failures must be exercised for stock-changing commands. Demonstrate that the same data survives application restart and database reload.

The handover for each increment includes: changed files and migrations; how to run the app and tests; synthetic demo scenarios; acceptance results by T reference; remaining decisions by O reference; and any limitations of simulated devices or integrations. Document technical assumptions separately from business requirements.

Before use with real stock, complete the production decisions for the deployed flows, perform backup and restore verification, and verify actual devices and labels. A local demo or scanner simulator is not a production release.

# Working alongside the consultancy

Keep this implementation specification separate from the consultancy draft. When the owner confirms a business decision, update the appropriate confirmed requirement and affected open decision, record its date, and revise the corresponding tests. Refresh the source baseline when requirements change rather than assuming these two documents synchronise automatically.

Maintain a small change log with requirement, previous behaviour, new decision, test impact, and implementation status. Do not resolve disagreements by silently overwriting either specification. Use the shared stock examples and acceptance scenarios to compare data integrity, workflow clarity, speed, recovery from mistakes, and usability between the two builds.

Use an independent repository or clearly separate implementation branch once the owner provides a development destination. No repository, hosting account, or deployment destination is selected by this document.

# First task to give the agent

> Read this Store App AI Agent Build Specification. Inspect the repository and its instructions, then report the existing stack and any conflicts with the confirmed requirements. Implement B0 and B1 as a runnable increment using synthetic data. Preserve the physical-stock versus book-record separation and the inward locks. Do not introduce purchase metal-rate tracking, old-tag imports, or an unlock override. Track open decisions by O reference and leave unresolved stock-changing actions unavailable. Provide migrations, run instructions, acceptance results and a short list of the next decisions needed. Continue with independent confirmed work when one decision is blocked.
