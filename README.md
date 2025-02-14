# ha-ica-todo
ICA integration for Home assistant


## Ideas

- [x] Shopping list picker for which lists to track
- [ ] Implement config flows step for Reauth / refresh tokens
- [x] Regex pattern matching for specifying Quantity and Unit
- [x] Assign due date based on current offer for items synced from ICA
- [ ] Assign appropriate ArticleGroupId. Using existing values in /common, /baseitems, or do a local or API lookup
- [ ] Get current offers in favorite stores. If any "productEan" matches one of my favorite products "baseitems", then automatically add it, with a due date
- [ ] Implement services and events to use for automations (notifications, etc.)
- [ ] Translate strings [se, en]

