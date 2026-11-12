"""Physical receipt records (C02) and the store-level physical stock ledger.

An Inward records goods actually received. It is not a supplier invoice; the
book side lives in the purchasing app and never touches these tables' stock
quantities.
"""

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q

from core.models import weight_field
from masters.models import Item, Karigar, Location, Purity, Supplier, Unit, Variety


class Inward(models.Model):
    SUPPLIER_PURCHASE = "supplier_purchase"
    SUPPLIER_APPROVAL = "supplier_approval"
    KARIGAR_INWARD = "karigar_inward"
    SOURCE_TYPES = [
        (SUPPLIER_PURCHASE, "Supplier purchase"),
        (SUPPLIER_APPROVAL, "Supplier approval memo"),
        (KARIGAR_INWARD, "Karigar inward"),
    ]
    SUPPLIER_SOURCES = (SUPPLIER_PURCHASE, SUPPLIER_APPROVAL)

    DRAFT = "draft"
    CONFIRMED = "confirmed"
    STATUSES = [(DRAFT, "Draft (not yet in stock)"), (CONFIRMED, "Received into stock")]

    LOCK_DIRECT_WEIGHT = "direct_weight_confirmed"
    LOCK_FIRST_LOT = "first_lot_created"
    LOCK_CAUSES = [
        (LOCK_DIRECT_WEIGHT, "Weight-only receipt was confirmed and added to stock"),
        (LOCK_FIRST_LOT, "First lot was created from this inward"),
    ]

    number = models.CharField(max_length=20, unique=True, null=True)
    source_type = models.CharField(max_length=24, choices=SOURCE_TYPES)
    supplier = models.ForeignKey(Supplier, null=True, blank=True, on_delete=models.PROTECT, related_name="inwards")
    karigar = models.ForeignKey(Karigar, null=True, blank=True, on_delete=models.PROTECT, related_name="inwards")
    source_reference = models.CharField(max_length=80, blank=True)
    source_date = models.DateField(null=True, blank=True)
    # One stock mode per inward until mixed receipts are decided (C02, O01).
    stock_mode = models.CharField(max_length=12, choices=Item.STOCK_MODES)
    location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name="+")
    custodian = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    notes = models.TextField(blank=True)

    status = models.CharField(max_length=12, choices=STATUSES, default=DRAFT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="+"
    )
    confirmed_at = models.DateTimeField(null=True)
    locked_at = models.DateTimeField(null=True)
    lock_cause = models.CharField(max_length=32, blank=True, choices=LOCK_CAUSES)
    version = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["-id"]
        constraints = [
            models.CheckConstraint(
                name="inward_source_party_matches_type",
                condition=(
                    Q(
                        source_type__in=["supplier_purchase", "supplier_approval"],
                        supplier__isnull=False,
                        karigar__isnull=True,
                    )
                    | Q(source_type="karigar_inward", karigar__isnull=False, supplier__isnull=True)
                ),
            ),
            models.CheckConstraint(
                name="inward_confirmation_consistent",
                condition=(
                    Q(status="draft", confirmed_at__isnull=True, confirmed_by__isnull=True)
                    | Q(status="confirmed", confirmed_at__isnull=False, confirmed_by__isnull=False)
                ),
            ),
            models.CheckConstraint(
                name="inward_lock_consistent",
                condition=(
                    Q(locked_at__isnull=True, lock_cause="")
                    | (Q(locked_at__isnull=False, status="confirmed") & ~Q(lock_cause=""))
                ),
            ),
            models.CheckConstraint(
                name="inward_weight_only_confirmed_is_locked",
                condition=~Q(stock_mode="weight_only", status="confirmed", locked_at__isnull=True),
            ),
        ]

    def __str__(self):
        return self.number or f"Inward #{self.pk}"

    @property
    def is_locked(self) -> bool:
        return self.locked_at is not None

    @property
    def is_confirmed(self) -> bool:
        return self.status == self.CONFIRMED

    @property
    def is_weight_only(self) -> bool:
        return self.stock_mode == Item.WEIGHT_ONLY

    @property
    def source_party(self):
        return self.supplier or self.karigar

    @property
    def needs_parcel_opening(self) -> bool:
        return self.source_type in self.SUPPLIER_SOURCES

    def active_lines(self):
        return [line for line in self.lines.all() if not line.is_removed]


class InwardLine(models.Model):
    inward = models.ForeignKey(Inward, on_delete=models.PROTECT, related_name="lines")
    line_no = models.PositiveIntegerField()
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="+")
    purity = models.ForeignKey(Purity, on_delete=models.PROTECT, related_name="+")
    variety = models.ForeignKey(Variety, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name="+")

    # What the source document says. Empty means "not stated", never zero.
    declared_pieces = models.PositiveIntegerField(null=True, blank=True)
    declared_gross_weight = weight_field(null=True, blank=True)
    declared_net_weight = weight_field(null=True, blank=True)

    # What was actually received and weighed. Weight-only stock uses the
    # gross column as its single weight and has no pieces or net weight.
    actual_pieces = models.PositiveIntegerField(null=True, blank=True)
    actual_gross_weight = weight_field()
    actual_net_weight = weight_field(null=True, blank=True)

    condition_notes = models.TextField(blank=True)
    # A line taken off a confirmed inward before its lock is kept for history.
    is_removed = models.BooleanField(default=False)

    class Meta:
        ordering = ["inward_id", "line_no"]
        constraints = [
            models.UniqueConstraint(fields=["inward", "line_no"], name="inward_line_no_unique"),
            models.CheckConstraint(name="inward_line_gross_positive", condition=Q(actual_gross_weight__gt=0)),
            models.CheckConstraint(
                name="inward_line_net_within_gross",
                condition=Q(actual_net_weight__isnull=True)
                | Q(actual_net_weight__gt=0, actual_net_weight__lte=models.F("actual_gross_weight")),
            ),
            models.CheckConstraint(
                name="inward_line_pieces_positive",
                condition=Q(actual_pieces__isnull=True) | Q(actual_pieces__gt=0),
            ),
            models.CheckConstraint(
                name="inward_line_declared_not_negative",
                condition=(Q(declared_gross_weight__isnull=True) | Q(declared_gross_weight__gte=0))
                & (Q(declared_net_weight__isnull=True) | Q(declared_net_weight__gte=0)),
            ),
        ]

    def __str__(self):
        return f"{self.inward} line {self.line_no}"

    @staticmethod
    def _difference(actual, declared):
        if actual is None or declared is None:
            return None
        return actual - declared

    @property
    def gross_difference(self) -> Decimal | None:
        """Actual minus source-declared weight. None when the source stated nothing."""
        return self._difference(self.actual_gross_weight, self.declared_gross_weight)

    @property
    def net_difference(self) -> Decimal | None:
        return self._difference(self.actual_net_weight, self.declared_net_weight)

    @property
    def pieces_difference(self) -> int | None:
        return self._difference(self.actual_pieces, self.declared_pieces)

    @property
    def classification(self) -> str:
        parts = [self.item.name, self.purity.name]
        if self.variety_id:
            parts.append(self.variety.name)
        return " · ".join(parts)


class StockMovement(models.Model):
    """Store-level physical stock ledger. Append-only (database trigger).

    Store physical stock is the sum of these rows. Allocation of that stock to
    lots, tags, locations and custodians is tracked separately and never adds
    to or subtracts from this ledger. Weight-only balances are a projection of
    these rows, not an editable total (C07).
    """

    INWARD_RECEIPT = "inward_receipt"
    INWARD_EDIT_ADJUSTMENT = "inward_edit_adjustment"
    KINDS = [
        (INWARD_RECEIPT, "Physical receipt"),
        (INWARD_EDIT_ADJUSTMENT, "Receipt edited before lock"),
    ]

    kind = models.CharField(max_length=32, choices=KINDS)
    stock_mode = models.CharField(max_length=12, choices=Item.STOCK_MODES)
    inward_line = models.ForeignKey(InwardLine, on_delete=models.PROTECT, related_name="movements")
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="+")
    purity = models.ForeignKey(Purity, on_delete=models.PROTECT, related_name="+")
    variety = models.ForeignKey(Variety, null=True, on_delete=models.PROTECT, related_name="+")
    unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name="+")
    location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name="+")

    # Signed quantities. Pieces and net weight are empty for weight-only stock.
    pieces = models.IntegerField(null=True)
    gross_weight = weight_field()
    net_weight = weight_field(null=True)

    occurred_at = models.DateTimeField(auto_now_add=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    source_command = models.CharField(max_length=64)
    retry_key = models.CharField(max_length=64)

    class Meta:
        ordering = ["id"]
        constraints = [
            # A receipt line enters physical stock once, whatever the retry behaviour.
            models.UniqueConstraint(
                fields=["inward_line"], condition=Q(kind="inward_receipt"), name="one_receipt_movement_per_line"
            ),
            models.CheckConstraint(
                name="movement_weight_only_has_no_pieces",
                condition=~Q(stock_mode="weight_only") | Q(pieces__isnull=True, net_weight__isnull=True),
            ),
        ]

    def __str__(self):
        return f"{self.kind} {self.gross_weight} {self.unit_id}"
