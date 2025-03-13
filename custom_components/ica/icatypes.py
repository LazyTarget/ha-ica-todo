from typing import TypedDict


class AuthCredentials(TypedDict):
    username: str
    password: str


class OAuthClient(TypedDict):
    client_id: str
    client_secret: str
    scope: str


class OAuthToken(TypedDict):
    """Represents the authentication state.

    Contains the OAuth client information, token, and user info.
    """

    id_token: str | None
    token_type: str
    access_token: str
    refresh_token: str
    scope: str
    expires_in: int
    # # Extra properties not defined in OAuth spec:
    expiry: str


class JwtUserInfo(dict):
    def __init__(self, decoded_jwt):
        self["given_name"] = decoded_jwt["given_name"]
        self["family_name"] = decoded_jwt["family_name"]
        self["person_name"] = (
            f"{decoded_jwt['given_name']} {decoded_jwt['family_name']}"
        )

    @property
    def person_name(self) -> str | None:
        return self["person_name"]


class AuthState(TypedDict):
    client: OAuthClient | None
    token: OAuthToken | None
    user: JwtUserInfo | None


class IcaBonusLevel(TypedDict):
    levelId: int
    pointValueFrom: int
    pointValueTom: int
    voucherValue: int


class IcaVoucher(TypedDict):
    title: str | None
    subTite: str | None
    description: str | None
    redeemedDate: str | None  # Only for used
    voucherCode: str | None  # example ["Monthly"]
    voucherType: str | None  # example ["Common"]
    sender: str | None  # example ["MonthlyBatch"]
    voucherAmount: int | None


class IcaVoucherList(TypedDict):
    active: list[IcaVoucher] | None
    used: list[IcaVoucher] | None


class IcaBalanceDetail(TypedDict):
    balanceDescription: str | None
    pointValue: int
    voucherValue: int
    sender: str | None


class IcaBalanceGroup(TypedDict):
    balanceCode: int | None
    balanceDescription: str | None
    pointValue: int
    voucherValue: int
    detailedBalances: list[IcaBalanceDetail] | None


class IcaAccountBalance(TypedDict):
    showPreliminaryBonus: bool | None
    preliminaryBonusText: str | None
    voucherMonth: str | None
    loyaltyMonth: str | None
    totalVoucherValue: int | None
    nextVoucherValue: int | None
    remainingPointsIncludingBoost: int | None
    remainingDays: int | None
    title: str | None
    groupedBalances: list[IcaBalanceGroup] | None


class IcaDiscountSummary(TypedDict):
    totalDiscount: int
    numberOfPurchases: int


class IcaAccountCurrentBonus(TypedDict):
    stammisBoostPreamble: str | None
    stammisBoostText: str | None
    stammisBoostBonusLevelText: str | None
    bonusLevels: list[IcaBonusLevel] | None
    vouchers: list[IcaVoucherList] | None
    accountBalance: IcaAccountBalance | None
    discountSummary: IcaDiscountSummary | None
    errorFetchingDiscount: bool | None


class Address(TypedDict):
    street: str | None
    zip: str | None
    city: str | None


class Coordinate(TypedDict):
    latitude: float | None
    longitude: float | None


class DayOpeningHours(TypedDict):
    title: str | None
    hours: str | None


class OpeningHours(TypedDict):
    today: str | None
    regularHours: list[DayOpeningHours] | None
    specialHours: list[DayOpeningHours] | None
    departmentHours: list[DayOpeningHours] | None
    serviceOpeningHours: list[DayOpeningHours] | None


class IcaStore(TypedDict):
    id: int  # "storeId"
    marketingName: str | None
    address: Address | None
    phone: str | None
    coordinates: Coordinate | None
    webURL: str | None
    openingHours: OpeningHours | None


class IcaArticleCategory(TypedDict):
    articleGroupName: str | None
    articleGroupId: int | None
    expandedArticleGroupName: str | None
    expandedArticleGroupId: int | None


class ArticleOfferEan(TypedDict):
    id: str | None  # "eanId"
    articleDescription: str | None
    imageUrl: str | None


class ArticleOfferStore(TypedDict):
    id: str | None  # "storeId"
    referencePriceText: str | None
    isValidInStore: bool | None
    isValidOnline: bool | None


class IcaOfferMechanics(TypedDict):
    type: str | None  # Example "Standard"
    quantity: float | None
    unitSign: str | None
    value1: str | None
    value2: str | None
    value3: str | None
    value4: str | None


class IcaStoreOffer(TypedDict):
    id: str | None  # "OfferId"
    category: IcaArticleCategory | None
    name: str | None  # "ArticleName / OfferName"
    brand: str | None
    packageInformation: str | None
    condition: str | None
    restriction: str | None
    referencePriceText: str | None
    isSelfScan: bool | None
    isPersonal: bool | None
    isUsed: bool | None
    isValidInStore: bool | None
    isValidOnline: bool | None
    validFrom: str | None
    validTo: str | None
    requiresLoyaltyCard: bool | None
    pictureUrl: str | None
    listImageUrl: str | None
    isProfileHighlight: bool | None
    isStoreHighlight: bool | None
    parsedMechanics: IcaOfferMechanics | None


class IcaArticleOffer(TypedDict):
    id: str | None  # "OfferId"
    category: IcaArticleCategory | None
    name: str | None  # "ArticleName / OfferName"
    brand: str | None
    packageInformation: str | None
    customerInformation: str | None
    condition: str | None
    disclaimer: str | None
    restriction: str | None
    referenceInfo: str | None
    isSelfScan: bool | None
    isPersonal: bool | None
    isUsed: bool | None
    eans: list[ArticleOfferEan] | None
    stores: list[ArticleOfferStore] | None
    validFrom: str | None
    validTo: str | None
    requiresLoyaltyCard: bool | None
    pictureUrl: str | None
    mediumImageUrl: str | None
    largeImageUrl: str | None
    parsedMechanics: IcaOfferMechanics | None


class ProductLookup(TypedDict):
    gtin: str  # "eanId / barcode"
    name: str  # "articleName"
    articleId: int | None
    articleGroupId: int | None
    expandedArticleGroupId: int | None


class IcaBaseItem(TypedDict):
    id: str  # "offlineId"
    text: str  # Freetext or ArticleName
    articleId: int | None
    articleGroupId: int | None
    articleGroupIdExtended: int | None
    articleEan: str | None
    sortOrder: int | None


# obsolete?
class IcaOffer(TypedDict):
    # OfferId: str | None
    id: str | None  # "OfferId"
    StoreId: int | None
    StoreIds: list[int] | None
    ArticleGroupId: int | None
    OfferType: str | None
    ImageUlr: str | None
    PriceComparison: str | None
    SizeOrQuantiry: str | None
    ProductName: str | None
    OfferTypeTitle: str | None
    Disclaimer: str | None
    OfferCondition: str | None
    LoadedOnCard: bool
    OfferUsed: bool
    Expired: bool
    # Articles: list[OfferArticle] | None


class OffersAndDiscountsForStore(TypedDict):
    discounts: list | None
    offers: list[IcaStoreOffer] | None


class IcaShoppingListEntryRecipeRef(TypedDict):
    id: int  # "recipeId"
    quantity: float
    unit: str


class IcaShoppingListEntry(TypedDict):
    id: int | None  # "RowId"
    offlineId: str | None
    productName: str
    quantity: float | None
    unit: str | None
    recipes: list[IcaShoppingListEntryRecipeRef] | None
    recipeId: str | None
    offerId: str | None
    isStrikedOver: bool
    internalOrder: int | None
    articleGroupId: int | None
    articleGroupIdExtended: int | None
    latestChange: str | None
    sourceId: int | None
    isSmartItem: bool | None


class IcaShoppingList(TypedDict):
    id: int | None
    offlineId: str | None
    title: str | None
    commentText: str | None
    sortingStore: int | None
    rows: list[IcaShoppingListEntry]
    latestChange: str | None
    isPrivate: bool | None
    isSmartList: bool | None


class IcaShoppingListSync(TypedDict):
    offlineId: str  # offlineId of the ShoppingList
    changedShoppingListProperties: dict[str, any] | None
    createdRows: list[IcaShoppingListEntry] | None
    changedRows: list[IcaShoppingListEntry] | None
    deletedRows: list[IcaShoppingListEntry] | None


class IcaProductCategory(TypedDict):
    Id: int | None
    Name: str | None
    ParentId: int | None
    LastSyncDate: str | None


class IcaArticle(TypedDict):
    id: int
    name: str
    pluralName: str | None
    parentId: int | None
    parentIdExtended: int | None
    status: int | None
    latestChange: str | None
    maxiFormatCategoryId: str | None
    maxiFormatCategoryName: str | None
    kvantumFormatCategoryId: str | None
    kvantumFormatCategoryName: str | None
    supermarketFormatCategoryId: str | None
    supermarketFormatCategoryName: str | None
    naraFormatCategoryId: str | None
    naraFormatCategoryName: str | None


class IcaCommonArticle(TypedDict):
    Id: int | None
    ProductName: str | None
    ArticleId: int | None
    ArticleGroupId: int | None
    ArticleGroupIdExtended: int | None
    FormatCategoryMaxi: str | None
    FormatCategoryKvantum: str | None
    FormatCategorySuperMarket: str | None
    FormatCategoryNara: str | None


class IcaFavoriteRecipe(TypedDict):
    RecipeId: int | None
    CreationDate: str | None


class IcaIngredient(TypedDict):
    Text: str | None
    IngredientsId: int | None
    Quantity: int | None
    Unit: str | None
    Ingredient: str | None


class IcaIngredientGroup(TypedDict):
    GroupName: str | None
    Ingredients: str | None


class IcaRecipe(TypedDict):
    Id: int | None
    Title: str | None
    ImageId: int | None
    YouTubeId: str | None
    IngredientGroups: list[IcaIngredientGroup]
    PreambleHTML: str | None
    CurrentUserRating: float | None
    AverageRating: float | None
    Difficulty: str | None
    CookingTime: str | None
    Portions: int | None
