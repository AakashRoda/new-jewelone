# Technical assumptions

These are engineering choices made to build confirmed behaviour. None of them is a business rule confirmed by the owner. Where one touches an open decision, the O reference is given and the choice was made so that it can be changed without losing data.

| # | Assumption | Why | Related |
| - | - | - | - |
| A1 | An inward is saved as a **draft** first and enters stock only when it is **confirmed**. | Gives the receiver a checking step before a weight-only receipt locks. A draft has no stock effect. | C02 |
| A2 | **Every** edit to a saved inward needs a reason, including edits to a draft. | The spec says editing before the lock needs a clear reason. The stricter reading was taken. | C02, C11 |
| A3 | Confirming a **supplier** receipt needs `parcel.open` in addition to `inward.create`. A karigar inward needs only `inward.create`. | "Only an authorised person may open a supplier parcel and verify its contents." Exact grants are open. | C02, O12 |
| A4 | One inward holds **either** tagged pieces **or** weight-only stock. A mixed parcel is entered as two inwards with the same source reference. | The lock behaviour of mixed inwards is open, so they are unavailable rather than guessed. Nothing is lost by splitting. | C02, O01 |
| A5 | Whether an item is tagged or weight-only is set on the **item master**. | A single obvious place. The metal/category/purity relationships are open. | C01, O04 |
| A6 | Weight-only stock has a **single weight** (no gross/net split and no piece count). | "Tracked by weight without individual pieces." | C07 |
| A7 | Weights are stored to **0.0001** of the unit and shown to 0.001. Input with more decimals is refused, never rounded. | Represents 10 mg and 0.001 ct exactly. Rounding boundaries are not agreed. | O02, O03 |
| A8 | Editing a received tagged-pieces inward before its lock **appends an adjustment** to the stock ledger; it does not rewrite the original receipt entry. | Keeps history and keeps physical stock equal to the corrected receipt. | C02 |
| A9 | A line removed from a received inward before its lock is **kept and marked removed**. | History is preserved; its quantity leaves stock through an adjustment. | C11 |
| A10 | Matching an invoice is a **link** between an invoice line and a receipt line, with no quantity of its own. | Full source matching is open; a link is enough to show the book side next to the physical side. | O11 |
| A11 | A wrong invoice link can be **removed with a reason**; the link row is kept. | No stock effect, and mistakes need a way out. | C02 |
| A12 | An entered supplier invoice **cannot be edited** yet. | Purchase details are open; avoiding an edit path avoids inventing rules for it. | O11 |
| A13 | Inward numbers are `INW-` plus a running number. | Routine technical choice. Tag numbering is a separate open decision. | O04 |
| A14 | All signed-in users can **view** stock, inwards, invoices and masters. Viewing the full history needs `audit.view`. | No view restrictions have been specified. | O12 |
| A15 | Times are shown in **Asia/Kolkata**; money is shown in rupees with Indian digit grouping. | The spec's examples are Indian (GST, HUID, ₹). | |
| A16 | `lot.create`, `tag.create` and the other later-stage permissions are **not defined yet**. | Only permissions that an existing command checks are listed, so the roles screen shows nothing that does nothing. | O12 |
| A17 | The first user of a non-demo installation gets access through a server command (`grant_full_access`), which is recorded in history. | There is deliberately no admin site and no superuser bypass. | C11, O12 |
