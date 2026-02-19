# 🏗️ MAPPA — Aplikacja Logistyki Budowlanej

## Status Projektu

> **Wersja:** 2.0  
> **Data:** 2026-02-18  
> **Lokalizacja:** `C:\Users\CabelJak\Desktop\MAPPA\`

---

## 📁 Struktura Plików

```
MAPPA/
├── app.py                        ← główna aplikacja Streamlit (jednoplikowa)
├── requirements.txt              ← zależności Python
├── cache_mechanicy.csv           ← auto-generowany cache geokodowania (po 1. uruchomieniu)
└── MAPPA_Dane/
    └── Dane_MAPPA.xlsx           ← plik z danymi (3 arkusze)
```

---

## 📊 Dane wejściowe (`Dane_MAPPA.xlsx`)

| Arkusz | Wierszy | Kolumny | Status |
|--------|---------|---------|--------|
| **MECHANICY** | 16 | Imię, Nazwisko, Kod pocztowy, Miasto, Ulica, Warsztat | ✅ Działa — Ulica jest pusta (NaN), obsługiwane |
| **BUDOWY** | 5 | NAZWA, KOST, WSPÓŁRZĘDNE | ✅ Działa — współrzędne parsowane ze stringa |
| **WARSZTATY** | 5 | NAZWA, WSPÓŁRZĘDNE | ✅ Dodany — niebieskie markery na mapie |

### Warsztaty w systemie:
- 1310 WKST TYCHY
- 1323 BOX KRAKÓW
- 1910 WKST KOMORNIKI
- 1222 BOX SULECHÓW
- *(+ ewentualnie 5. z Excela)*

### Budowy w systemie:
- BUDOWA MIKOŁÓW (KOST: 1111)
- BUDOWA KRAKÓW (KOST: 2222)
- BUDOWA ZAKOPANE (KOST: 3333)
- BUDOWA SANDOMIERZ (KOST: 4444)
- BUDOWA RACIBÓRZ (KOST: 5555)

---

## ✅ Co DZIAŁA

| Funkcja | Opis |
|---------|------|
| 🗺️ **Mapa Folium** | Pełna szerokość, 3 warstwy markerów + warstwa tras |
| 👷 **Mechanicy (zielone)** | Geokodowani z adresu (Kod pocztowy + Miasto), ikona: user |
| 🏢 **Budowy (czerwone)** | Parsowanie współrzędnych ze stringa, popup z NAZWA + KOST |
| 🔧 **Warsztaty (niebieskie)** | Nowy arkusz, parsowanie współrzędnych, ikona: wrench |
| 🔀 **LayerControl** | Włączanie/wyłączanie warstw: Budowy, Warsztaty, Mechanicy, Trasy |
| 🛣️ **Trasy OSRM** | Kolorowe polilinie rysowane na mapie po wyborze budowy |
| 📊 **Tabela wyników** | Sortowana rosnąco wg dystansu, podświetlony najlepszy wynik |
| 🏆 **Najlepszy wybór** | Zielona karta z najkrótszym dojazdem |
| ⛽ **Kalkulator kosztów** | Cena paliwa (PLN/l) + Spalanie (l/100km) → automatyczny koszt/km |
| 🔧 **Filtr warsztatów** | Multiselect — wybór z którego warsztatu mechanicy |
| 📥 **Eksport CSV** | Pobieranie raportu z aktualną tabelą (dystans, czas, koszt) |
| 💾 **Cache geokodowania** | `cache_mechanicy.csv` — przyspiesza restart o ~90% |
| 📈 **Metryki nad mapą** | 4 karty: Mechanicy ogółem, Wybranych, Budowy, Warsztaty |
| 🔧 **Podział wg warsztatów** | Tabela: ile mechaników, śr. dystans, śr. koszt per warsztat |
| 🇵🇱 **Interfejs po polsku** | Cały UI w języku polskim |

---

## ❌ Czego NIE MA (do ewentualnego dodania)

| Funkcja | Komentarz |
|---------|-----------|
| 📦 **Kompilacja .exe** | Kod jest PyInstaller-ready, ale `.exe` nie został jeszcze zbudowany. Komenda: `pyinstaller --onefile app.py` |
| 🔄 **Odświeżanie danych** | Zmiana danych w Excelu wymaga restartu apki (lub wyczyszczenia cache Streamlit) |
| 🗺️ **Trasa warsztat→budowa** | Obecnie trasy idą: mechanik (dom) → budowa. Brak trasy: warsztat → budowa |
| 📱 **Responsywność mobilna** | Zoptymalizowane pod desktop, na telefonie może być ciasno |
| 🔐 **Logowanie** | Brak autoryzacji — każdy z dostępem do folderu uruchomi apkę |
| 📊 **Historia raportów** | Brak zapisu historii wygenerowanych raportów |

---

## ⚠️ Znane Ograniczenia

| Temat | Szczegóły |
|-------|-----------|
| **Nominatim rate-limit** | 1 zapytanie/sekundę — pierwsze uruchomienie z 16 mechanikami trwa ~18 sek. Kolejne starty korzystają z cache. |
| **OSRM publiczny serwer** | Darmowy, ale może być wolny lub niedostępny. Brak gwarancji uptime. |
| **Ulica = pusta** | Kolumna Ulica jest NaN — geokodowanie bazuje na Kod pocztowy + Miasto. Dokładność do poziomu miasta/wsi. |
| **Kodowanie znaków** | Polskie znaki w kolumnach (WSPÓŁRZĘDNE) — obsługa inteligentna, ale zależna od zapisania Excela w UTF-8. |

---

## 🚀 Uruchomienie

```powershell
# Jednorazowo — instalacja zależności
cd C:\Users\CabelJak\Desktop\MAPPA
py -m pip install -r requirements.txt

# Start aplikacji
py -m streamlit run app.py
```

Aplikacja otworzy się w przeglądarce pod `http://localhost:8501`

---

## 📦 Kompilacja do .exe (opcjonalnie)

```powershell
py -m pip install pyinstaller
pyinstaller --onefile --hidden-import=streamlit --hidden-import=folium app.py
```

> [!WARNING]
> Streamlit w `.exe` wymaga dodatkowej konfiguracji (włożenie plików statycznych do bundle). Rekomendowane jest uruchamianie przez `streamlit run app.py`.
