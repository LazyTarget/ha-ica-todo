from typing import TypedDict
import datetime


class AuthCredentials:
    username: str
    password: str

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password


class OAuthClient:
    client_id: str
    client_secret: str
    scope: str

    def __init__(self, client_id: str, client_secret: str, scope: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.scope = scope


class OAuthToken:
    """Represents the authentication state.

    Contains the OAuth client information, token, and user info.
    """

    id_token: str | None
    token_type: str | None
    access_token: str | None
    refresh_token: str | None
    scope: str | None
    expires_in: int | None
    # Properties not defined in OAuth spec:
    expiry: datetime.datetime | None

    def refresh(self, refresh_token: "OAuthToken"):
        self.token_type = refresh_token.token_type
        self.access_token = refresh_token.access_token
        self.refresh_token = refresh_token.refresh_token
        self.scope = refresh_token.scope
        self.expires_in = refresh_token.expires_in


class JwtUserInfo:
    person_name: str | None

    def __init__(self, decoded_jwt):
        self.person_name = f"{decoded_jwt['given_name']} {decoded_jwt['family_name']}"


class AuthState:
    Client: OAuthClient | None
    Token: OAuthToken | None
    JwtUserInfo: JwtUserInfo | None


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
    RowId: int | None
    ProductName: str | None
    Quantity: float | None
    SourceId: int | None
    IsStrikedOver: bool
    InternalOrder: int | None
    ArticleGroupId: int | None
    ArticleGroupIdExtended: int | None
    LatestChange: str | None
    OfflineId: str | None
    IsSmartItem: bool


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
