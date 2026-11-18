import asyncio
from decimal import Decimal

import pytest

from starter import recommend_price, sample_fetch_offers


def run_recommendation(offers, current='100.00', minimum='50.00', status='success'):
    async def fetch_offers():
        return {'status': status, 'offers': offers}

    return asyncio.run(recommend_price(fetch_offers, Decimal(current), Decimal(minimum)))


def test_regular_calculation():
    result = asyncio.run(recommend_price(
        sample_fetch_offers, Decimal('5000.00'), Decimal('4500.00'),
    ))

    assert result['price'] == Decimal('4728.00')
    assert result['decision'] == 'APPLY'
    assert result['reason']


@pytest.mark.parametrize('status', ['partial', 'error'])
def test_unsuccessful_status(status):
    result = run_recommendation(
        [{'seller': 'other', 'price': Decimal('10.00'), 'delivery_days': 1}],
        status=status,
    )

    assert result['price'] == Decimal('100.00')
    assert result['decision'] == 'HOLD'
    assert result['reason']


def test_source_exception():
    async def fetch_offers():
        raise ConnectionError('Источник недоступен')

    result = asyncio.run(recommend_price(fetch_offers, Decimal('100.00'), Decimal('50.00')))

    assert result['price'] == Decimal('100.00')
    assert result['decision'] == 'HOLD'


def test_timeout():
    async def fetch_offers():
        await asyncio.sleep(0.1)
        return {'status': 'success', 'offers': []}

    result = asyncio.run(recommend_price(
        fetch_offers, Decimal('100.00'), Decimal('50.00'), timeout_s=0.001,
    ))

    assert result['price'] == Decimal('100.00')
    assert result['decision'] == 'HOLD'


def test_no_valid_offers():
    result = run_recommendation([
        {'seller': 'MYSHOP', 'price': Decimal('10.00'), 'delivery_days': 1},
        {'seller': 'other', 'price': Decimal('20.00'), 'delivery_days': 7},
        {'seller': 'other', 'price': Decimal('30.00'), 'delivery_days': None},
    ], minimum='120.00')

    assert result['price'] == Decimal('100.00')
    assert result['decision'] == 'HOLD'


def test_delivery_six_days_and_round_down():
    result = run_recommendation([
        {'seller': 'MYSHOP', 'price': Decimal('1.00'), 'delivery_days': 1},
        {'seller': 'other', 'price': Decimal('100.01'), 'delivery_days': 6},
        {'seller': 'other', 'price': Decimal('2.00'), 'delivery_days': 7},
    ])

    assert result['price'] == Decimal('98.50')
    assert result['decision'] == 'APPLY'


def test_minimum_price():
    result = run_recommendation([
        {'seller': 'other', 'price': Decimal('90.00'), 'delivery_days': 1},
    ], minimum='95.00')

    assert result['price'] == Decimal('95.00')
    assert result['decision'] == 'APPLY'


@pytest.mark.parametrize(
    ('competitor', 'minimum', 'expected', 'decision'),
    [
        ('130.00', '130.00', '130.00', 'APPLY'),
        ('70.00', '70.00', '70.00', 'APPLY'),
        ('140.00', '140.00', '140.00', 'REVIEW'),
        ('70.00', '50.00', '68.95', 'REVIEW'),
    ],
)
def test_change_threshold(competitor, minimum, expected, decision):
    result = run_recommendation([
        {'seller': 'other', 'price': Decimal(competitor), 'delivery_days': 1},
    ], minimum=minimum)

    assert result['price'] == Decimal(expected)
    assert result['decision'] == decision
