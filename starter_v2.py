from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal
from enum import Enum
from typing import TypedDict


class Status(str, Enum):
    SUCCESS = 'success'
    PARTIAL = 'partial'
    ERROR = 'error'


class Decision(str, Enum):
    APPLY = 'APPLY'
    REVIEW = 'REVIEW'
    HOLD = 'HOLD'


class OfferData(TypedDict):
    seller: str
    price: Decimal
    delivery_days: int | None


class FetchResultData(TypedDict):
    status: str
    offers: list[OfferData]


class RecommendationData(TypedDict):
    price: Decimal
    decision: str
    reason: str


FetchOffers = Callable[[], Awaitable[FetchResultData]]

DISCOUNT = Decimal('0.015')
MAX_CHANGE = Decimal('0.30')
KOPECK = Decimal('0.01')
MAX_DELIVERY_DAYS = 6
OUR_SELLER = 'myshop'


@dataclass(frozen=True, slots=True)
class Offer:
    seller: str
    price: Decimal
    delivery_days: int | None

    @classmethod
    def from_dict(cls, data: OfferData) -> Offer:
        return cls(**data)

    def is_eligible(self) -> bool:
        return (
            self.delivery_days is not None
            and self.delivery_days <= MAX_DELIVERY_DAYS
            and self.seller.casefold() != OUR_SELLER
        )


@dataclass(frozen=True, slots=True)
class Recommendation:
    price: Decimal
    decision: Decision
    reason: str

    def to_dict(self) -> RecommendationData:
        return {
            'price': self.price,
            'decision': self.decision.value,
            'reason': self.reason,
        }


class PriceRecommender:
    def __init__(
        self,
        fetch_offers: FetchOffers,
        current_price: Decimal,
        min_price: Decimal,
        timeout_s: float = 2.0,
    ) -> None:
        self._fetch_offers = fetch_offers
        self._current_price = current_price
        self._min_price = min_price
        self._timeout_s = timeout_s

    async def calculate(self) -> Recommendation:
        try:
            data = await asyncio.wait_for(self._fetch_offers(), timeout=self._timeout_s)
        except asyncio.TimeoutError:
            return self._hold('Источник не ответил вовремя')
        except Exception:
            return self._hold('Ошибка получения предложений')

        if data['status'] != Status.SUCCESS.value:
            return self._hold('Источник вернул неполные данные или ошибку')

        offers = self._select_offers(data['offers'])
        if not offers:
            return self._hold('Нет подходящих предложений')

        price = self._calculate_price(offers)
        return self._decide(price)

    @staticmethod
    def _select_offers(data: list[OfferData]) -> list[Offer]:
        offers = (Offer.from_dict(item) for item in data)
        return [offer for offer in offers if offer.is_eligible()]

    def _calculate_price(self, offers: list[Offer]) -> Decimal:
        competitor_price = min(offer.price for offer in offers)
        price = (competitor_price * (Decimal('1') - DISCOUNT)).quantize(
            KOPECK, rounding=ROUND_DOWN,
        )
        return max(price, self._min_price)

    def _decide(self, price: Decimal) -> Recommendation:
        if abs(price - self._current_price) > self._current_price * MAX_CHANGE:
            return Recommendation(
                price=price,
                decision=Decision.REVIEW,
                reason='Изменение цены больше 30%: нужна ручная проверка',
            )
        return Recommendation(
            price=price,
            decision=Decision.APPLY,
            reason='Цена рассчитана по предложениям конкурентов',
        )

    def _hold(self, reason: str) -> Recommendation:
        return Recommendation(
            price=self._current_price,
            decision=Decision.HOLD,
            reason=reason,
        )


async def recommend_price(
    fetch_offers: FetchOffers,
    current_price: Decimal,
    min_price: Decimal,
    timeout_s: float = 2.0,
) -> RecommendationData:
    result = await PriceRecommender(
        fetch_offers, current_price, min_price, timeout_s,
    ).calculate()
    return result.to_dict()


async def sample_fetch_offers() -> FetchResultData:
    return {
        'status': Status.SUCCESS.value,
        'offers': [
            {'seller': 'myshop', 'price': Decimal('4300.00'), 'delivery_days': 2},
            {'seller': 'Competitor A', 'price': Decimal('4800.00'), 'delivery_days': 3},
            {'seller': 'Competitor B', 'price': Decimal('4900.00'), 'delivery_days': 6},
            {'seller': 'Competitor C', 'price': Decimal('4400.00'), 'delivery_days': 7},
            {'seller': 'Competitor D', 'price': Decimal('4500.00'), 'delivery_days': None},
        ],
    }


async def main() -> None:
    result = await recommend_price(
        sample_fetch_offers,
        current_price=Decimal('5000.00'),
        min_price=Decimal('4500.00'),
    )
    print(result)


if __name__ == '__main__':
    asyncio.run(main())
