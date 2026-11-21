# Heatwise pitch deck

13 slides: the problem (heat and homes), Heatwise, the app and Luke, results, and the real room.

**Present it:** open `index.html` in a browser (or serve this folder, e.g. `python3 -m http.server -d pitch`, or turn on GitHub Pages for `/pitch`).

- → / space / click the right of the screen: next reveal, then next slide. ← / click the left: back.
- **N**: show or hide the speaker notes.
- `index.html#slide-7` opens slide 7.

## Files

| Path | What |
|---|---|
| `slides/<id>.html` | One slide each, with its speaker notes in `<aside>`. **This is the source.** |
| `deck.json` | Slide order, sections, fonts |
| `deck.css` | Shared styles |
| `images/` | The two seminar-room renders (from the LiDAR scan) |
| `build.py` | Builds `index.html` from the above |
| `index.html` | Generated. Don't edit it by hand. |

After changing a slide, rebuild:

```bash
python3 pitch/build.py
```

The slides were made in Claude's Slides editor, which is where they look best and can export to PowerPoint or PDF. The files here are a copy of that deck as of 21 Nov 2026. `index.html` is close to it but not identical: icons are simple symbols here.

## Sources for the numbers

Checked on 21 Nov 2026.

| Slide | Claim | Source |
|---|---|---|
| Heat | 37% of energy-related CO₂ comes from heat (2024); heat is about half of final energy use | [IEA, Renewables 2025: renewable heat](https://www.iea.org/reports/renewables-2025/renewable-heat) |
| Heat | Transport about 30%, electricity about 20% of final energy (2021) | [IEA, Renewables 2021: renewable heat](https://www.iea.org/reports/renewables-2021/renewable-heat) |
| Top 10 | Global greenhouse gas share by sector, 2016 (road 11.9%, homes 10.9%, …, chemicals 3.6%) | [Our World in Data, Climate Watch / WRI](https://ourworldindata.org/ghg-emissions-by-sector) |
| UK homes | 18% of UK greenhouse gas emissions come from heating homes (2021) | [National Audit Office, Decarbonising home heating (2024)](https://www.nao.org.uk/reports/decarbonising-home-heating/) |
| Results | 15% cheaper, 13% less CO₂, comfortable 97% vs 70% of the time | Our simulation: `python -m heatwise.compare_timers` (5-room house, DECISIONS D29) |
