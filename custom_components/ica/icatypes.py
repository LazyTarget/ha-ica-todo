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


class Address(TypedDict):
    Street: str | None
    Zip: str | None
    City: str | None


class Coordinate(TypedDict):
    Latitude: float | None
    Longitude: float | None


class DayOpeningHours(TypedDict):
    Title: str | None
    Hours: str | None


class OpeningHours(TypedDict):
    Today: str | None
    RegularHours: list[DayOpeningHours] | None
    SpecialHours: list[DayOpeningHours] | None
    OtherOpeningHours: list[DayOpeningHours] | None


class IcaStore(TypedDict):
    Id: int | None
    MarketingName: str | None
    Address: Address | None
    Phone: str | None
    Coordinates: Coordinate | None
    WebURL: str | None
    FacebookUrl: str | None
    FilterItems: list[int] | None
    ProfileId: str | None
    OpeningHours: OpeningHours | None


class OfferArticle(TypedDict):
    EanId: str | None
    ArticleDescription: str | None


class IcaOffer(TypedDict):
    OfferId: str | None
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
    Articles: list[OfferArticle] | None


class IcaShoppingListEntry(TypedDict):
    id: int | None # RowId
    offlineId: str | None
    productName: str
    quantity: float | None
    isStrikedOver: bool
    internalOrder: int | None
    articleGroupId: int | None
    articleGroupIdExtended: int | None
    latestChange: str | None
    sourceId: int | None
    isSmartItem: bool | None


class IcaShoppingList(TypedDict):
    Id: int | None
    Title: str | None
    CommentText: str | None
    SortingStore: int | None
    Rows: list[IcaShoppingListEntry] | None
    LatestChange: str | None
    OfflineId: str | None
    IsPrivate: bool | None
    IsSmartList: bool | None


class IcaProductCategory(TypedDict):
    Id: int | None
    Name: str | None
    ParentId: int | None
    LastSyncDate: str | None


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
