from dataclasses import dataclass

@dataclass(frozen=True)
class DefectType:
    name: str
    color: str  


DEFAULT_DEFECTS: list[DefectType] = [
    DefectType("Fehlstelle nicht benetzt",      "#ff0000"),
    DefectType("Fehlstelle partiell benetzt",   "#ff7700"),
    DefectType("Krisseliges Zinn",              "#00ff00"),
    DefectType("Kratzer funktional",            "#00ffea"),
    DefectType("Kratzer kosmetisch",            "#00aeff"),
    DefectType("Kurzschlüsse",                  "#0066ff"),
    DefectType("Verunreinigungen",              "#9900ff"),
    DefectType("Lackfehler",                    "#e100ff"),
    DefectType("Abgeplatzter Lack",             "#ff00aa"),
    DefectType("Streifenbildung",               "#F7B259"),
    DefectType("Bohrung nicht freigeblasen",    "#31a354",),
]