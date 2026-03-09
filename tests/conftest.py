"""
Pytest Fixture'ları — Tüm testlerin ortak yapı taşları.

Neden conftest.py?
  Aynı fixture'ı her test dosyasına kopyalamak yerine
  pytest bunu otomatik bulur ve enjekte eder.
  Fixture değiştiğinde tek yerde değişir.
"""
import pytest

from sera_ai.domain.models import (
    BitkilProfili, SeraKonfig, SistemKonfig, SensorOkuma
)
from sera_ai.domain.state_machine import SeraStateMachine
from sera_ai.domain.circuit_breaker import CircuitBreaker
from sera_ai.application.event_bus import EventBus
from sera_ai.drivers.mock import MockSahaNode
from sera_ai.merkez.mock import MockMerkez


# ── Bitki Profilleri ──────────────────────────────────────────

@pytest.fixture
def profil_domates() -> BitkilProfili:
    return BitkilProfili(
        isim="Domates", min_T=15, max_T=30, opt_T=23,
        min_H=60, max_H=85, opt_CO2=1000, hasat_gun=90,
    )

@pytest.fixture
def profil_marul() -> BitkilProfili:
    return BitkilProfili(
        isim="Marul", min_T=10, max_T=22, opt_T=16,
        min_H=65, max_H=85, opt_CO2=800, hasat_gun=45,
    )


# ── Sensör Okumaları ──────────────────────────────────────────

@pytest.fixture
def sensor_normal(profil_domates) -> SensorOkuma:
    """Domates için tamamen normal değerler."""
    return SensorOkuma(
        sera_id="s1", T=23.0, H=72.0, co2=950,
        isik=450, toprak_nem=500, ph=6.5, ec=1.8,
    )

@pytest.fixture
def sensor_yuksek_sicaklik(profil_domates) -> SensorOkuma:
    """Uyarı eşiği üzerinde sıcaklık (opt_T + 4 = 27°C)."""
    return SensorOkuma(
        sera_id="s1", T=27.0, H=72.0, co2=950,
        isik=450, toprak_nem=500, ph=6.5, ec=1.8,
    )

@pytest.fixture
def sensor_alarm_sicaklik(profil_domates) -> SensorOkuma:
    """max_T üzerinde sıcaklık → ALARM."""
    return SensorOkuma(
        sera_id="s1", T=31.0, H=72.0, co2=950,
        isik=450, toprak_nem=500, ph=6.5, ec=1.8,
    )

@pytest.fixture
def sensor_acil_sicaklik(profil_domates) -> SensorOkuma:
    """Kritik eşik → ACİL_DURDUR."""
    return SensorOkuma(
        sera_id="s1", T=34.0, H=72.0, co2=950,
        isik=450, toprak_nem=500, ph=6.5, ec=1.8,
    )

@pytest.fixture
def sensor_gecersiz() -> SensorOkuma:
    """Fiziksel sınır dışı — sensör arızası simülasyonu."""
    return SensorOkuma(
        sera_id="s1", T=-999.0, H=72.0, co2=950,
        isik=450, toprak_nem=500, ph=6.5, ec=1.8,
    )


# ── Sistem Bileşenleri ────────────────────────────────────────

@pytest.fixture
def event_bus() -> EventBus:
    return EventBus()

@pytest.fixture
def state_machine(profil_domates, event_bus) -> SeraStateMachine:
    return SeraStateMachine("s1", profil_domates, olay_bus=event_bus)

@pytest.fixture
def circuit_breaker() -> CircuitBreaker:
    """5 hata eşiği, 60s recovery."""
    return CircuitBreaker("test_cb", hata_esigi=5, recovery_sn=60)

@pytest.fixture
def circuit_breaker_dusuk() -> CircuitBreaker:
    """3 hata eşiği — hızlı açılır (test kolaylığı)."""
    return CircuitBreaker("test_cb_dusuk", hata_esigi=3, recovery_sn=60)


# ── Mock Donanım ──────────────────────────────────────────────

@pytest.fixture
def mock_node_hatasiz(profil_domates) -> MockSahaNode:
    """Hiç hata vermeyen mock node."""
    node = MockSahaNode("s1", profil_domates,
                        sensor_hata_orani=0.0, komut_hata_orani=0.0)
    node.baglan()
    return node

@pytest.fixture
def mock_merkez(profil_domates) -> MockMerkez:
    node = MockSahaNode("s1", profil_domates,
                        sensor_hata_orani=0.0, komut_hata_orani=0.0)
    merkez = MockMerkez()
    merkez.node_ekle("s1", node)
    merkez.baslat()
    return merkez


# ── Konfigürasyon ─────────────────────────────────────────────

@pytest.fixture
def sistem_konfig(profil_domates) -> SistemKonfig:
    return SistemKonfig(
        seralar=[
            SeraKonfig("s1", "Sera A", 500, "Domates", saha_donanim="mock"),
        ],
        profiller={"Domates": profil_domates},
        merkez_donanim="mock",
    )
