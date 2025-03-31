# ha-ica-todo

ICA integration for Home assistant. 
Forked from https://github.com/dennisgranasen/ha-ica-todo. But very much rewritten since...

NOTE: Currently under development and might be unstable!


## User Stories

- [x] Regex pattern matching for specifying Quantity and Unit
- [x] Assign due date based on current offer for items synced from ICA
- [x] Assign appropriate ArticleGroupId. Using existing values in /common, /baseitems, or do a local or API lookup
- [x] Get current offers in favorite stores. If any "productEan" matches one of my favorite products "baseitems", then automatically add it, with a due date => Can be done by writing an automation and listening on ica_event

**Integration**
- [x] Shopping list picker for which lists to track
- [ ] Implement services and events to use for automations (notifications, etc.)
- [ ] Translate strings [se, en]
- [ ] Implement config flows step for Reauth / refresh tokens
- [x] Update config entry with token, if doing full auth
- [x] Refresh login when expiry was passed
- [x] Refresh login when 401 was returned during fetching of data
- [x] Invoke a new login if an attempted "Refresh login", failed
- [x] Implement Blueprint automation for tracking new offers

**Shopping lists**
- [x] Categorize added items into the correct article group!
- [ ] Time limited offers to be automatically added (if exists under favorites)
- [ ] Checking off items should sync between store-lists (including time limited offers)
- [ ] Adding items to Trello checklist should create them in the "Master"-list
- [ ] Adding items to a shopping list  should sync them to Trello checklist too?
- [ ] User should use the "store"-list when shopping, which should contain existing offers for that store, and the wanted items from "Master"-list
- [ ] Adding items to the "Master"-list should calculate the sum of quantities and update accordingly
- [ ] Implement the different `CONFLICT_MODES`
- [ ] Allow for (scheduled) notification, when favorite item(s) are on discount/offer
- [ ] Avoid getting all shopping lists before updating individual lists. Since integration has config on the ID's. Only fetch during config_flow

**Barcode/QR/Bower**
- [ ] Check API possibilities for scanning/shopping items with the phone?
- [ ] Check if can integrate with the 'Bower recycling app'

**Recipes**
- [ ] Able to export Ica recipe into Trello
- [ ] Find recipes that match ingredients that are currently on offer (or in a shopping list)
- [ ] Service to list recipes possible with the current pantry inventory

**Docs**
- [ ] Document installation/configuration
- [ ] Document use-case examples
- [ ] Document Automation examples
