import asyncio
from decimal import Decimal, ROUND_DOWN


async def recommend_price(fetch_offers, current_price, min_price, timeout_s=2.0):
    try:
        result = await asyncio.wait_for(fetch_offers(), timeout=timeout_s)
    except Exception:
        return {'price': current_price, 'decision': 'HOLD', 'reason': 'Не удалось получить цены'}

    if result['status'] != 'success':
        return {'price': current_price, 'decision': 'HOLD', 'reason': 'Данные источника неполные'}

    prices = [
        offer['price']
        for offer in result['offers']
        if offer['delivery_days'] is not None
        and offer['delivery_days'] <= 6
        and offer['seller'].lower() != 'myshop'
    ]

    if not prices:
        return {'price': current_price, 'decision': 'HOLD', 'reason': 'Нет подходящих предложений'}

    price = (min(prices) * Decimal('0.985')).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
    price = max(price, min_price)
    decision = 'REVIEW' if abs(price - current_price) > current_price * Decimal('0.30') else 'APPLY'
    reason = 'Изменение цены больше 30%' if decision == 'REVIEW' else 'Цена рассчитана'
    return {'price': price, 'decision': decision, 'reason': reason}


async def sample_fetch_offers():
    return {
        'status': 'success',
        'offers': [
            {'seller': 'myshop', 'price': Decimal('4300.00'), 'delivery_days': 2},
            {'seller': 'Competitor A', 'price': Decimal('4800.00'), 'delivery_days': 3},
            {'seller': 'Competitor B', 'price': Decimal('4900.00'), 'delivery_days': 6},
            {'seller': 'Competitor C', 'price': Decimal('4400.00'), 'delivery_days': 7},
            {'seller': 'Competitor D', 'price': Decimal('4500.00'), 'delivery_days': None},
        ],
    }


async def main():
    result = await recommend_price(
        sample_fetch_offers,
        current_price=Decimal('5000.00'),
        min_price=Decimal('4500.00'),
    )
    print(result)


if __name__ == '__main__':
    asyncio.run(main())
