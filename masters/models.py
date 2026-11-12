"""Master records (C01).

The final relationship between metal, category and purity, and the final
validation rules, are an open decision (O04). These masters are therefore kept
simple and independent: a receipt line picks an item and a purity, and
optionally a variety of that item.
"""

from django.db import models

from core.models import percent_field, weight_field


class Master(models.Model):
    is_active = models.BooleanField(default=True, help_text="Inactive records stay in history but cannot be picked.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Unit(Master):
    WEIGHT = "weight"
    COUNT = "count"
    KINDS = [(WEIGHT, "Weight"), (COUNT, "Count")]

    code = models.CharField(max_length=8, unique=True, help_text="For example g, ct, Nos.")
    name = models.CharField(max_length=40)
    kind = models.CharField(max_length=8, choices=KINDS)
    grams_per_unit = weight_field(
        null=True, blank=True, help_text="Explicit conversion to grams for weight units (g = 1, ct = 0.2)."
    )

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.code


class Metal(Master):
    name = models.CharField(max_length=40, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Purity(Master):
    metal = models.ForeignKey(Metal, on_delete=models.PROTECT, related_name="purities")
    name = models.CharField(max_length=40, unique=True, help_text="For example Gold 22K.")
    percentage = percent_field(
        null=True, blank=True, help_text="Physical purity percentage, for example 91.6. Not a charging factor."
    )

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "purities"

    def __str__(self):
        return self.name


class HsnCode(Master):
    code = models.CharField(max_length=12, unique=True)
    description = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "HSN reference"

    def __str__(self):
        return self.code


class Item(Master):
    TAGGABLE = "taggable"
    WEIGHT_ONLY = "weight_only"
    STOCK_MODES = [
        (TAGGABLE, "Tagged pieces (each piece gets its own tag)"),
        (WEIGHT_ONLY, "Weight-only stock (no tags, no piece count)"),
    ]

    name = models.CharField(max_length=60, unique=True, help_text="For example Chain, Ring, Gold Balls.")
    stock_mode = models.CharField(max_length=12, choices=STOCK_MODES)
    weight_unit = models.ForeignKey(Unit, on_delete=models.PROTECT, related_name="+")
    hsn = models.ForeignKey(HsnCode, null=True, blank=True, on_delete=models.PROTECT, related_name="items")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Variety(Master):
    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="varieties")
    name = models.CharField(max_length=60, help_text="For example Machine Chain, Hollow Chain.")

    class Meta:
        ordering = ["item__name", "name"]
        verbose_name_plural = "varieties"
        constraints = [models.UniqueConstraint(fields=["item", "name"], name="variety_unique_per_item")]

    def __str__(self):
        return f"{self.item.name} – {self.name}"


class MakingChargeRule(Master):
    """Named making-charge rule.

    Units, bases, rounding and defaults for charges are open (O03), so this
    master holds no formula yet.
    """

    SUPPLIER_PAID = "supplier_paid"
    CUSTOMER_CHARGEABLE = "customer_chargeable"
    APPLIES_TO = [
        (SUPPLIER_PAID, "Making charge paid to the supplier"),
        (CUSTOMER_CHARGEABLE, "Making charge chargeable to the customer"),
    ]

    name = models.CharField(max_length=80, unique=True)
    applies_to = models.CharField(max_length=24, choices=APPLIES_TO)
    item = models.ForeignKey(Item, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ChargeDefinition(Master):
    """An other-charge type created by the business (C06), not by a shopper."""

    name = models.CharField(max_length=80, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "other-charge definition"

    def __str__(self):
        return self.name


class Supplier(Master):
    name = models.CharField(max_length=120, unique=True)
    gstin = models.CharField("GSTIN", max_length=15, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Karigar(Master):
    name = models.CharField(max_length=120, unique=True)
    phone = models.CharField(max_length=20, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Location(Master):
    """A place stock can be held. The real location list is open (O06)."""

    name = models.CharField(max_length=60, unique=True)
    is_demo = models.BooleanField(default=False, help_text="Demo location, not an agreed store location (O06).")

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class PolicySetting(models.Model):
    """A named numeric setting whose production value is a business decision.

    Demo values let confirmed flows be exercised without claiming that the
    owner has agreed the number (O02).
    """

    DEMO = "demo"
    CONFIRMED = "confirmed"
    STATUSES = [(DEMO, "Demo value, needs a decision"), (CONFIRMED, "Confirmed by the owner")]

    key = models.CharField(max_length=80, unique=True)
    label = models.CharField(max_length=120)
    value = weight_field()
    unit = models.CharField(max_length=24)
    status = models.CharField(max_length=12, choices=STATUSES, default=DEMO)
    decision_ref = models.CharField(max_length=8, blank=True, help_text="Open decision this depends on, e.g. O02.")
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["key"]

    def __str__(self):
        return self.key
