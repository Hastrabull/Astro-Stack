"""In-app help manual with chapter navigation."""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTextBrowser,
    QListWidget, QListWidgetItem, QPushButton, QSplitter,
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtGui import QFont

# ---------------------------------------------------------------------------
# Chapter content (HTML)
# ---------------------------------------------------------------------------

CHAPTERS: dict[str, tuple[str, str]] = {
    # key: (menu label, HTML body)

    "stack_settings": (
        "Stack Settings",
        """
<h2>Stack Settings</h2>
<p>Sekcja <b>Stack Settings</b> pozwala wybrać algorytm łączenia klatek świetlnych
(Lights) w jeden obraz wynikowy oraz dostosować jego parametry.
Przed stackowaniem aplikacja automatycznie buduje klatki kalibracyjne
(Bias, Dark, Flat) jeśli zostały dodane.</p>
<p>Kliknij przycisk <b>▶ Stack</b>, aby uruchomić cały pipeline.</p>
""",
    ),

    "algorithm": (
        "  › Algorithm",
        """
<h2>Algorithm</h2>
<p>Wybór metody matematycznej, którą aplikacja stosuje do połączenia
nakładających się pikseli ze wszystkich klatek w jeden wynikowy piksel.</p>

<h3>Mean (Średnia)</h3>
<p>Oblicza zwykłą średnią arytmetyczną wartości pikseli ze wszystkich klatek.
Najszybsza metoda, ale wrażliwa na outliers (samoloty, satelity, gorące piksele).
Nadaje się do krótkich sesji z małą liczbą klatek.</p>

<h3>Median</h3>
<p>Wybiera wartość środkową z posortowanej listy pikseli.
Odporna na pojedyncze bardzo jasne lub bardzo ciemne piksele.
Dobry kompromis między prędkością a jakością — zalecana metoda podstawowa.</p>

<h3>Sigma Clipping</h3>
<p>Iteracyjnie oblicza średnią i odchylenie standardowe, a następnie odrzuca
piksele odchylające się bardziej niż <i>sigma × σ</i> od średniej.
Po odrzuceniu outliers oblicza nową średnią z pozostałych pikseli.
Najlepsza metoda do usuwania śladów satelitów i gorących pikseli.</p>

<h3>Kappa-Sigma</h3>
<p>Wariant Sigma Clipping z osobnym parametrem <i>Kappa</i> zamiast sigma.
Działanie identyczne — nazwa pochodzi z tradycji astrofotograficznej.
Użyj gdy chcesz jawnie kontrolować próg odrzucania przez parametr <b>Sigma / Kappa</b>.</p>
""",
    ),

    "sigma": (
        "  › Sigma / Kappa",
        """
<h2>Sigma / Kappa</h2>
<p>Próg odrzucania pikseli w algorytmach <b>Sigma Clipping</b> i <b>Kappa-Sigma</b>.
Aktywny tylko gdy wybrany jest jeden z tych algorytmów.</p>

<p>Wartość określa, ile odchyleń standardowych (σ) od średniej musi się różnić
piksel, żeby zostać uznany za outlier i odrzucony.</p>

<ul>
  <li><b>Niska wartość (np. 1.5–2.0)</b> — agresywne odrzucanie,
      usuwa więcej pikseli, może odrzucić prawdziwy sygnał.</li>
  <li><b>Typowa wartość (2.5–3.0)</b> — dobry kompromis,
      usuwa satelity i gorące piksele bez strat w sygnale.</li>
  <li><b>Wysoka wartość (4.0+)</b> — łagodne odrzucanie,
      tylko skrajne outliers są usuwane.</li>
</ul>

<p><b>Zalecana wartość:</b> 3.0</p>
""",
    ),

    "iterations": (
        "  › Iterations",
        """
<h2>Iterations</h2>
<p>Liczba iteracji pętli sigma clipping. Aktywna tylko dla algorytmów
<b>Sigma Clipping</b> i <b>Kappa-Sigma</b>.</p>

<p>Po każdej iteracji odrzucone piksele są usuwane, a próg sigma
jest przeliczany na podstawie pozostałych pikseli. Kolejne iteracje
coraz precyzyjniej oczyszczają stos.</p>

<ul>
  <li><b>1–2</b> — szybko, wystarczające przy dobrej jakości klatek.</li>
  <li><b>3–5</b> — standardowe ustawienie, dobry balans.</li>
  <li><b>10+</b> — bardzo dokładne, ale znacznie wolniejsze.</li>
</ul>

<p><b>Zalecana wartość:</b> 5</p>
""",
    ),

    "stretch": (
        "Stretch",
        """
<h2>Stretch</h2>
<p>Sekcja <b>Stretch</b> pozwala poprawić widoczność wynikowego obrazu po stackowaniu.
Surowy obraz astronomiczny ma zwykle bardzo mały zakres dynamiczny skupiony
blisko zera — bez stretchingu wygląda niemal czarno.</p>

<p>Stretch przekształca wartości pikseli tak, by uwidocznić szczegóły mgławic,
galaktyk i gwiazd. Działa na kopii obrazu — oryginał surowy jest zawsze zachowany
(eksport TIFF 16-bit zapisuje dane sprzed stretchingu).</p>

<p>Wybierz zakładkę odpowiadającą preferowanej metodzie i kliknij <b>Apply</b>.</p>
""",
    ),

    "auto_stf": (
        "  › Auto STF",
        """
<h2>Auto STF (Screen Transfer Function)</h2>
<p>Automatyczny stretch inspirowany algorytmem STF z PixInsight.
Jednym kliknięciem dopasowuje punkt środkowy krzywej tonalnej
tak, by tło nieba znalazło się na poziomie ~25% jasności,
a jasne obiekty nie były przepalone.</p>

<h3>Jak działa?</h3>
<ol>
  <li>Oblicza medianę i MAD (Median Absolute Deviation) obrazu.</li>
  <li>Wyznacza punkty cięcia (c0, c1) na podstawie mediany i rozrzutu.</li>
  <li>Stosuje korekcję gamma tak, by mediana lądowała w okolicach 25%.</li>
</ol>

<h3>Kiedy używać?</h3>
<p>Jako szybki podgląd zaraz po stackowaniu.
Dla finalnej obróbki przejdź do zakładki <b>Levels</b> lub <b>Curves</b>
i dostosuj ręcznie.</p>
""",
    ),

    "levels": (
        "  › Levels",
        """
<h2>Levels (Poziomy)</h2>
<p>Ręczna kontrola punktu czarnego, białego i gammy — analogicznie
do narzędzia Levels w Photoshopie.</p>

<h3>Black point (punkt czarny)</h3>
<p>Wartość pikseli uznana za absolutną czerń. Wszystko poniżej tej wartości
zostanie ucięte do 0. Przesuń w górę, żeby rozjaśnić tło nieba
i ukryć gradient jasności.</p>

<h3>White point (punkt biały)</h3>
<p>Wartość pikseli uznana za absolutną biel. Wszystko powyżej zostanie ucięte do 1.
Przesuń w dół, żeby rozjaśnić obraz bez zmiany tła.</p>

<h3>Gamma</h3>
<p>Krzywa nieliniowa środkowych tonów. Wartość > 1 rozjaśnia,
wartość < 1 przyciemnia, wartość = 1 to brak korekcji (liniowa).</p>

<ul>
  <li><b>Gamma 1.0</b> — brak korekcji</li>
  <li><b>Gamma 1.5–2.2</b> — typowe rozjaśnienie mgławic</li>
  <li><b>Gamma 0.5</b> — przyciemnienie prześwietlonych obszarów</li>
</ul>
""",
    ),

    "curves": (
        "  › Curves",
        """
<h2>Curves (Krzywe tonalne)</h2>
<p>Zaawansowana kontrola jasności przez dowolną krzywą tonalną,
definiowaną zestawem punktów kontrolnych (input → output).</p>

<h3>Jak używać?</h3>
<ol>
  <li>Tabela zawiera pary wartości: <b>Input</b> (0–1) → <b>Output</b> (0–1).</li>
  <li>Edytuj komórki tabeli, wpisując żądane wartości.</li>
  <li>Aplikacja interpoluje krzywą sześcienną (PCHIP) między punktami.</li>
  <li>Kliknij <b>Apply</b>, żeby zastosować.</li>
  <li>Kliknij <b>Reset</b>, żeby wrócić do krzywej liniowej.</li>
</ol>

<h3>Przykłady</h3>
<ul>
  <li><b>S-curve (kontrast)</b>: (0,0), (0.25, 0.15), (0.5, 0.5), (0.75, 0.85), (1,1)</li>
  <li><b>Rozjaśnienie</b>: (0,0), (0.5, 0.7), (1,1)</li>
  <li><b>Wyciągnięcie tła</b>: (0, 0.05), (0.5, 0.6), (1,1)</li>
</ul>
""",
    ),

    "hist_eq": (
        "  › Histogram EQ",
        """
<h2>Histogram Equalisation</h2>
<p>Wyrównuje histogram obrazu za pomocą dystrybuanty (CDF — Cumulative Distribution Function).
Automatycznie redistrybuuje wartości pikseli tak, żeby każdy zakres jasności
był równo reprezentowany.</p>

<h3>Efekt</h3>
<p>Znacząco zwiększa kontrast w ciemnych obszarach obrazu kosztem
ewentualnego przepalenia jasnych obiektów. Dobra metoda do wydobycia
delikatnych struktur w rozległych mgławicach.</p>

<h3>Uwagi</h3>
<ul>
  <li>Dla obrazów kolorowych equalizacja odbywa się niezależnie dla każdego kanału R/G/B.</li>
  <li>Może powodować zmiany kolorów — jeśli to problem, użyj Levels lub STF.</li>
  <li>Nie ma parametrów — wynik jest w pełni automatyczny.</li>
</ul>
""",
    ),

    "histogram": (
        "  › Histogram (wykres)",
        """
<h2>Histogram</h2>
<p>Wykres rozkładu jasności pikseli w aktualnie wyświetlanym obrazie.
Aktualizuje się automatycznie po każdej operacji stretchingu.</p>

<h3>Jak czytać histogram?</h3>
<ul>
  <li><b>Oś X</b> — wartość jasności piksela (0 = czarny, 1 = biały).</li>
  <li><b>Oś Y</b> — liczba pikseli o danej jasności.</li>
  <li>Dla obrazów kolorowych: <span style="color:#ff6666">czerwony</span>,
      <span style="color:#66ff66">zielony</span>,
      <span style="color:#6699ff">niebieski</span> kanał osobno.</li>
</ul>

<h3>Interpretacja</h3>
<ul>
  <li>Słupki skupione przy 0 → obraz zbyt ciemny, potrzebny stretch.</li>
  <li>Słupki przy 1 → przepalenie, zmniejsz White point w Levels.</li>
  <li>Równomierny rozkład → dobry stretch.</li>
</ul>
""",
    ),
}

# ---------------------------------------------------------------------------
# Dialog
# ---------------------------------------------------------------------------

class HelpDialog(QDialog):
    _instance: "HelpDialog | None" = None

    @classmethod
    def show_chapter(cls, parent, chapter_key: str):
        """Open (or reuse) the help dialog and jump to chapter_key."""
        if cls._instance is None or not cls._instance.isVisible():
            cls._instance = cls(parent)
        cls._instance.go_to(chapter_key)
        cls._instance.raise_()
        cls._instance.activateWindow()
        cls._instance.show()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AstroStack — Help")
        self.resize(820, 560)
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowMinimizeButtonHint
        )

        layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left — chapter list
        self._chapter_list = QListWidget()
        self._chapter_list.setMaximumWidth(210)
        self._chapter_list.setMinimumWidth(160)
        for key, (label, _) in CHAPTERS.items():
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, key)
            self._chapter_list.addItem(item)
        self._chapter_list.currentItemChanged.connect(self._on_chapter_selected)

        # Right — content browser
        self._browser = QTextBrowser()
        self._browser.setOpenExternalLinks(False)
        self._browser.setReadOnly(True)

        splitter.addWidget(self._chapter_list)
        splitter.addWidget(self._browser)
        splitter.setSizes([190, 610])
        layout.addWidget(splitter)

    def go_to(self, chapter_key: str):
        keys = list(CHAPTERS.keys())
        if chapter_key not in keys:
            chapter_key = keys[0]
        idx = keys.index(chapter_key)
        self._chapter_list.setCurrentRow(idx)
        self._render(chapter_key)

    def _on_chapter_selected(self, current, previous):
        if current is None:
            return
        key = current.data(Qt.ItemDataRole.UserRole)
        self._render(key)

    def _render(self, key: str):
        _, html = CHAPTERS[key]
        full_html = f"""
        <html><head><style>
          body {{ font-family: Segoe UI, sans-serif; font-size: 13px;
                 color: #ddd; background: #1e1e1e; padding: 12px; }}
          h2 {{ color: #4fc3f7; border-bottom: 1px solid #444; padding-bottom: 4px; }}
          h3 {{ color: #aaa; margin-top: 14px; }}
          ul, ol {{ margin-left: 18px; }}
          li {{ margin-bottom: 4px; }}
          b {{ color: #eee; }}
          code {{ background: #2a2a2a; padding: 1px 4px; border-radius: 3px; }}
        </style></head><body>{html}</body></html>
        """
        self._browser.setHtml(full_html)
