# Protokol klávesnice CZC.Gaming Hexblade

Zjištěno reverzním inženýrstvím původního softwaru *CZC G GK1000* (SONiX
„Gaming Force Z“, `GamingKeyboardWriter.dll`, `SonixHidDll.dll`) a ověřeno na
skutečné klávesnici.

## Zařízení

* USB `0c45:8006` („SONiX USB DEVICE“), firmware bcdDevice 1.12
* rozhraní 0 = klávesnice + **64bajtový HID feature report bez report ID**
  (usage page 0x0C) – konfigurační kanál
* rozhraní 1 = multimédia, systém, NKRO, myš

Každý příkaz je `SetFeature` (64 B). Odpověď se čte `GetFeature` (64 B);
`reply[3] == 0x01` znamená ACK. Mezi příkazy čeká původní SW 15 ms.

## Zápis bloku

```
→ 04 <cmd> 00 00 00 00 00 00 <počet paketů u16 LE> 00 …   (hlavička)
← 04 <cmd> 00 01 …                                          (ACK)
→ N × 64 B dat
→ 04 02
← 04 02 00 01 <součet všech bajtů dat u32 LE>               (kontrola)
```

| cmd  | obsah                 | velikost |
|------|-----------------------|----------|
| 0x11 | mapování kláves       | 0x280 B (10 paketů) |
| 0x13 | podsvícení            | 0x480 B (18 paketů) |
| 0x15 | makra                 | proměnná (tabulka 50 × 8 B + kroky po 4 B) |
| 0x17 | 64 B nastavení (neznámé, s barvou) | 0x40 B |

Další příkazy: `04 05 … [8]=2` (čtení informací o zařízení), `04 18` / `04 19`
(vstup do režimu / výstup z něj, význam nejasný), `04 ab` (challenge–response
autentizace originality zařízení; pro zápis není potřeba).

## Matice kláves

Klávesy i LED jsou adresované maticí **8 řádků × 18 sloupců**; index
`row * 18 + col`. Pozice jsou v `hexblade/layout.py`. Klávesy nad numerickým
blokem: Vol+ (0,14), Vol− (0,15), Mute (0,16), Kalkulačka (6,1).

## Blok podsvícení (0x13, 0x480 B)

| offset | obsah |
|--------|-------|
| 0x000–0x1FF | 32 záznamů režimů × 16 B (sloty 0–18 = efekty 1–19, slot 19 = vlastní barvy) |
| 0x200–0x43F | 144 × 4 B barvy kláves: `80 R G B` |
| 0x440–0x44F | záznam **aktivního** režimu (kopie jednoho ze slotů) |
| 0x450–0x47F | nuly |

Záznam režimu (16 B):

| bajt | význam |
|------|--------|
| 0 | číslo režimu: 1–19, 0x80 = vlastní barvy |
| 1–3 | barva R, G, B |
| 4–6 | druhá barva R, G, B – u reaktivních efektů (2, 3, 15 …) **barva pozadí** mezi stisky; původní SW ji nikdy neposílá |
| 7 | 1 = druhá barva zapnutá (0 = pozadí zhasnuté) |
| 8 | 1 = „plné barvy“ = náhodné / duhové barvy (hodnota 2 dělá totéž) |
| 9 | jas 1–16 |
| 10 | rychlost 1–16 |
| 11 | směr 0–3 |
| 14–15 | `AA 55` |

Režimy: 1 Static, 2 SingleOn, 3 SingleOff, 4 Glittering, 5 Falling,
6 Colourful, 7 Breath, 8 Spectrum, 9 Outward, 10 Scrolling, 11 Rolling,
12 Rotating, 13 Explode, 14 Launch, 15 Ripples, 16 Flowing, 17 Pulsating,
18 Tilt, 19 Shuttle.

Když je aktivní záznam samé nuly, klávesnice zhasne.

Ověřeno: reaktivní efekty umí jen jednobarevné pozadí. Vlastní barvy kláves
(0x200–0x43F) firmware používá jen v režimu 0x80. Nepomáhá ani bajt 8 = 1/2,
ani bajt 7 = 2.

## Blok mapování kláves (0x11, 0x280 B)

144 × 4 B (index z matice), zbytek nuly, na offsetu 0x27E podpis `AA 55`.
**Bez podpisu klávesnice blok přijme, ale použije výchozí mapování.**
Modifikátory se kódují jen bitem (`02 01 00 00` = levý Ctrl). Kódy:

| kód | význam |
|-----|--------|
| `00 00 00 00` | výchozí funkce klávesy |
| `02 <mod> <usage> 00` | klávesa (HID usage), `mod` = bitová maska Ctrl/Shift/Alt/Win (L: 01/02/04/08, R: 10/20/40/80) |
| `03 <lo> <hi> 00` | consumer usage (multimédia), např. `03 cd 00` = Play/Pause |
| `01 01 <btn> 00` | tlačítko myši (01 L, 02 P, 04 prostřední, 08 zpět, 10 vpřed) |
| `01 03 01/ff 00` | kolečko nahoru / dolů |
| `04 01/02/04 00` | pravděpodobně systémové (power/sleep/wake) – neověřeno |
| `06 …` | makro |
