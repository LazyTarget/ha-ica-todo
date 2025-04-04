# Scenario

## 0. Reviewing current inventory

This step is about checking what items we currently have, and if any items have been spoiled. Then toss it away and add it to the shoppping list if required. Which is something that Grocy keeps track of by its Due Dates and Minimum stock-features.

This will be less and less important to do manually, since Grocy will take over much of this work.


## 1. Meal prep

User prepares for the upcoming week by planning the recipies to cook.
Using the Grocy interface, one can see which recipes/items that are in the inventory, and sort by the "due score".

Once user has a few meals, missing items can be placed in the Grocy shopping list.

> EVENT: "GrocyShoppingListUpdated"
> Here we can sync items to the shopping list in ICA

**Todos:**

- [ ] Implement a sync to ICA


## 2. In the store

### 2a. Scanning items in the store

The user, can either:
- use the Grocy shopping list
- or the ICA-app
- or Home Assistant to-do list
- or (and possibly the simplest) is to use the in-store scanners which integrate directly with the ICA shopping lists

### 2b. After purchase

Once at the register and user pay for the items. A reciept is created in Kivra.
This pdf-file could be exported and placed in a folder. Possibly a seperate integration can listen to this folder, and automatically process these receipts.

> EVENT: "NewReciept"
> Here we can go through the reciept and trigger a "Purchase" inside of Grocy.
> Looking up Grocy product id, using Barcode or Name. Store name could possibly be parsed for assigning the appropriate Grocy store.
> Determining the amount based on the reciept row (article quantity * number of articles)
> Best before will now be set based on the Reciept date + Default due date for this particular product


## (3. Once home)

Once the user gets home and sorts the items into their respective location. Example: Pantry, Fridge, Freezer.

> EVENT: "OrganizingProducts"
> Here we have a chance of correcting due dates, and specifying where the product will be stored.


## 4. Cooking

When cooking, the user could use the Grocy app to look up the recipe. Also handy feature for changing the desired servings.

Once cooked, the user can consume all products for this recipe.

Now the circle is complete!



## Extras

### Barcode Buddy

Barcode Buddy can simply making updates to Grocy using barcodes instead of having to navigate through the Grocy interface.

Currently, barcode buddy doesn't give the option of manually specifying Amount, Due Date or Price. Those fields get set automatically based on product preferences.

Barcode Buddy has a custom mapping between Product, Barcode and Quantity. So for each scan, it will add the specified quantity, and the Unit inside Grocy will be used.


**Todos:**
- [ ] Implement ICA barcode lookup handler (Private)
- [ ] Implement Kivra recipt to Barcode Buddy scanner

Barcode Buddy has a federation server that could 'crowd source' barcodes and their product info.



## Adding product info to Grocy

Being constistent and adding price info to the purchased products, will give a handy Price graph to the items. As well as cost information about recipies.

Adding Calory info on products will give that information to the recipe.



### ICA offers

The ICA Home Assistant integration can notify when new offers are posted for your favorite ICA stores.

> EVENT: "ICA_NEW_OFFERS"
> Here we could automatically add these offers to your ICA shopping list. Since that is quite simple to do and is already possible with the provided Home Assistant Blueprint.
> But Grocy won't know about these offer products. Only once they are added through step 2b or step 2a and user scans them with Grocy directly.


### Recipe import

- [ ] Import ICA recipies into Grocy

