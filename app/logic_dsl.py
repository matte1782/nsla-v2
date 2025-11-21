from __future__ import annotations

"""
Core DSL definition shared across modules (Phase 1 requirement).

- DSL version constant (used by translator/pipeline).
- Canonical sort and predicate catalogues.
- Helper utilities for validation and discovery.

Reference document: `resources/nsla_v2/logic_dsl_v2.md`.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

DSL_VERSION: str = "2.1"


@dataclass(frozen=True)
class SortSpec:
    name: str
    description: str
    extends: Optional[str] = None


@dataclass(frozen=True)
class PredicateSpec:
    name: str
    args: List[str]
    description: str
    synonyms: List[str]


SORTS: Dict[str, SortSpec] = {
    "Entity": SortSpec("Entity", "Sort generica di fallback per input non canonico"),
    "Soggetto": SortSpec("Soggetto", "Parte generica di un rapporto giuridico"),
    "Debitore": SortSpec("Debitore", "Parte obbligata all'adempimento", extends="Soggetto"),
    "Creditore": SortSpec("Creditore", "Parte titolare della pretesa", extends="Soggetto"),
    "Professionista": SortSpec("Professionista", "Operatore professionale", extends="Debitore"),
    "Consumatore": SortSpec("Consumatore", "Persona fisica che agisce per scopi estranei all'attività professionale", extends="Soggetto"),
    "Vettore": SortSpec("Vettore", "Soggetto che esegue il trasporto di cose o persone", extends="Soggetto"),
    "Speditore": SortSpec("Speditore", "Soggetto che affida il bene al vettore", extends="Soggetto"),
    "Destinatario": SortSpec("Destinatario", "Soggetto che riceve il bene trasportato", extends="Soggetto"),
    "Mittente": SortSpec("Mittente", "Soggetto che consegna la merce al vettore", extends="Soggetto"),
    "Contratto": SortSpec("Contratto", "Accordo negoziale"),
    "Prestazione": SortSpec("Prestazione", "Oggetto dell'obbligazione"),
    "Danno": SortSpec("Danno", "Pregiudizio economico o non patrimoniale"),
    "Evento": SortSpec("Evento", "Fatto rilevante ai fini causali"),
    "Bene": SortSpec("Bene", "Oggetto materiale o immateriale di diritti"),
    "BeneRegistrato": SortSpec("BeneRegistrato", "Bene mobile soggetto a registrazione", extends="Bene"),
    "Marchio": SortSpec("Marchio", "Segno distintivo registrato", extends="Bene"),
    "Testamento": SortSpec("Testamento", "Atto di ultima volontà"),
    "Titolo": SortSpec("Titolo", "Documento astrattamente idoneo a trasferire diritti"),
    "Possesso": SortSpec("Possesso", "Situazione di fatto corrispondente all'esercizio di un diritto reale"),
    "MisuraCautelare": SortSpec("MisuraCautelare", "Misura cautelare personale o reale"),
    "Pena": SortSpec("Pena", "Sanzione penale"),
    "Procedura": SortSpec("Procedura", "Sequenza di atti processuali/amministrativi"),
    "StrutturaSanitaria": SortSpec("StrutturaSanitaria", "Ente sanitario contrattualmente obbligato", extends="Soggetto"),
}


PREDICATES: Dict[str, PredicateSpec] = {
    "Contratto": PredicateSpec(
        "Contratto",
        ["Contratto"],
        "Esistenza di un contratto specifico",
        ["contratto valido", "contratto esistente"],
    ),
    "HaObbligo": PredicateSpec(
        "HaObbligo",
        ["Debitore", "Creditore", "Contratto"],
        "Il debitore ha un obbligo verso il creditore derivante da un contratto specifico.",
        ["ha obbligo", "obbligo contrattuale", "rapporto obbligatorio"],
    ),
    "ContrattoValido": PredicateSpec(
        "ContrattoValido",
        ["Debitore", "Contratto"],
        "Il contratto tra le parti è valido ai sensi degli artt. 1325 ss. c.c.",
        ["validità contratto", "requisiti contratto"],
    ),
    "Consenso": PredicateSpec(
        "Consenso",
        ["Soggetto", "Contratto"],
        "Consenso manifestato validamente dalle parti (artt. 1325-1326 c.c.).",
        ["accordo di volontà"],
    ),
    "CapacitaContrattuale": PredicateSpec(
        "CapacitaContrattuale",
        ["Soggetto"],
        "Capacità di agire necessaria a stipulare il contratto (art. 1425 c.c.).",
        ["capacità di agire"],
    ),
    "CausaLegittima": PredicateSpec(
        "CausaLegittima",
        ["Contratto"],
        "Causa lecita del contratto (art. 1343 c.c.).",
        ["causa lecita"],
    ),
    "OggettoDeterminato": PredicateSpec(
        "OggettoDeterminato",
        ["Contratto"],
        "Oggetto possibile e determinato/determinabile (art. 1346 c.c.).",
        ["oggetto determinato"],
    ),
    "FormaPrescritta": PredicateSpec(
        "FormaPrescritta",
        ["Contratto"],
        "Forma ad substantiam richiesta dalla legge o dalle parti (artt. 1350 ss. c.c.).",
        ["forma richiesta"],
    ),
    "Inadempimento": PredicateSpec(
        "Inadempimento",
        ["Debitore", "Contratto"],
        "Il debitore non adempie alla prestazione contrattuale",
        ["violazione contratto", "mancato adempimento"],
    ),
    "Adempimento": PredicateSpec(
        "Adempimento",
        ["Debitore", "Contratto"],
        "Il debitore esegue correttamente la prestazione",
        ["esecuzione prestazione"],
    ),
    "Mora": PredicateSpec(
        "Mora",
        ["Debitore"],
        "Ritardo nell'adempimento imputabile al debitore",
        ["mora debendi"],
    ),
    "DovereDiligenza": PredicateSpec(
        "DovereDiligenza",
        ["Debitore", "Prestazione"],
        "Standard di diligenza richiesto (art. 1176 c.c.).",
        ["standard professionale"],
    ),
    "ComportamentoDiligente": PredicateSpec(
        "ComportamentoDiligente",
        ["Debitore", "Prestazione"],
        "Condotta conforme al dovere di diligenza.",
        ["condotta diligente"],
    ),
    "Colpa": PredicateSpec(
        "Colpa",
        ["Debitore", "Evento"],
        "Violazione del dovere di diligenza che rende imputabile l'evento.",
        ["negligenza"],
    ),
    "Imputabilita": PredicateSpec(
        "Imputabilita",
        ["Debitore", "Contratto"],
        "L'inadempimento è imputabile al debitore",
        ["colpa del debitore"],
    ),
    "ResponsabileColpa": PredicateSpec(
        "ResponsabileColpa",
        ["Debitore", "Danno"],
        "Il debitore è responsabile per colpa di un danno specifico.",
        ["responsabilità per colpa"],
    ),
    "ResponsabilitaContrattuale": PredicateSpec(
        "ResponsabilitaContrattuale",
        ["Debitore", "Creditore", "Contratto"],
        "Il debitore risponde contrattualmente verso il creditore",
        ["responsabilità per inadempimento"],
    ),
    "ResponsabilitaCivileColpa": PredicateSpec(
        "ResponsabilitaCivileColpa",
        ["Soggetto", "Danno"],
        "Responsabilità civile da fatto illecito colposo (art. 2043 c.c.).",
        ["responsabilità aquiliana"],
    ),
    "ResponsabilitaMedicaContrattuale": PredicateSpec(
        "ResponsabilitaMedicaContrattuale",
        ["StrutturaSanitaria", "Soggetto"],
        "Responsabilità contrattuale della struttura sanitaria verso il paziente.",
        ["responsabilità medica"],
    ),
    "DannoPatrimoniale": PredicateSpec(
        "DannoPatrimoniale",
        ["Soggetto"],
        "Il soggetto subisce un danno economicamente valutabile",
        ["perdita economica"],
    ),
    "NessoCausale": PredicateSpec(
        "NessoCausale",
        ["Evento", "Danno"],
        "Relazione causale tra evento e danno",
        ["collegamento causale"],
    ),
    "Risarcimento": PredicateSpec(
        "Risarcimento",
        ["Debitore", "Creditore", "Danno"],
        "Obbligo del debitore di risarcire il creditore per un danno specifico",
        ["risarcimento del danno", "indennizzo"],
    ),
    "RisarcimentoIllecito": PredicateSpec(
        "RisarcimentoIllecito",
        ["Soggetto", "Soggetto", "Danno"],
        "Obbligo risarcitorio da fatto illecito (art. 2043 c.c.).",
        ["responsabilità aquiliana"],
    ),
    "DifettoConformita": PredicateSpec(
        "DifettoConformita",
        ["Bene"],
        "Difetto del bene rispetto al contratto (art. 129 Codice del Consumo).",
        ["difetto di conformità"],
    ),
    "DirittoSceltaRemedy": PredicateSpec(
        "DirittoSceltaRemedy",
        ["Consumatore", "Bene"],
        "Diritti del consumatore alla garanzia legale (art. 130 Codice del Consumo).",
        ["diritti garanzia legale"],
    ),
    "ContrattoAdesione": PredicateSpec(
        "ContrattoAdesione",
        ["Contratto"],
        "Contratto predisposto unilateralmente dal professionista (art. 1341 c.c.).",
        ["contratto di adesione"],
    ),
    "PredeterminatoDa": PredicateSpec(
        "PredeterminatoDa",
        ["Contratto", "Professionista"],
        "Clausole predisposte dal professionista.",
        ["predisposto da"],
    ),
    "NonNegoziabileDa": PredicateSpec(
        "NonNegoziabileDa",
        ["Contratto", "Consumatore"],
        "Clausole non negoziabili dal consumatore.",
        ["non negoziabile"],
    ),
    "PuoSoloAccettareOppureRifiutare": PredicateSpec(
        "PuoSoloAccettareOppureRifiutare",
        ["Consumatore", "Contratto"],
        "Il consumatore può solo aderire integralmente o rifiutare.",
        ["take it or leave it"],
    ),
    "TrascrizioneOpponibileATerzi": PredicateSpec(
        "TrascrizioneOpponibileATerzi",
        ["Contratto"],
        "Trascrizione opponibile per i contratti preliminari (art. 2645-bis c.c.).",
        ["opponibilità trascrizione"],
    ),
    "PossessoContinuato": PredicateSpec(
        "PossessoContinuato",
        ["Soggetto", "Bene"],
        "Possesso continuo e non interrotto (art. 1158 c.c.).",
        ["possesso continuativo"],
    ),
    "PossessoPubblico": PredicateSpec(
        "PossessoPubblico",
        ["Soggetto", "Bene"],
        "Possesso pacifico e manifesto richiesto per l'usucapione.",
        ["possesso pacifico"],
    ),
    "AnimusDomini": PredicateSpec(
        "AnimusDomini",
        ["Soggetto", "Bene"],
        "Esercizio del possesso come se si fosse proprietari (animus domini).",
        ["animo del proprietario", "animus domini"],
    ),
    "DurataPossesso": PredicateSpec(
        "DurataPossesso",
        ["Soggetto", "Bene"],
        "Durata del possesso utile ai fini dell'usucapione (es. venti anni).",
        ["durata possesso", "duratapossesso20anni"],
    ),
    "BuonaFede": PredicateSpec(
        "BuonaFede",
        ["Soggetto"],
        "Buona fede nel possesso (art. 1147 c.c.).",
        ["buona fede"],
    ),
    "TitoloIdoneo": PredicateSpec(
        "TitoloIdoneo",
        ["Titolo", "BeneRegistrato"],
        "Titolo astrattamente idoneo al trasferimento (art. 1153 c.c.).",
        ["titolo valido"],
    ),
    "UsucapioneOrdinaria": PredicateSpec(
        "UsucapioneOrdinaria",
        ["Soggetto", "Bene"],
        "Acquisto ventennale della proprietà (art. 1158 c.c.).",
        ["usucapione ventennale"],
    ),
    "UsucapioneAbbreviata": PredicateSpec(
        "UsucapioneAbbreviata",
        ["Soggetto", "BeneRegistrato"],
        "Usucapione abbreviata di beni mobili registrati (art. 1153 c.c.).",
        ["usucapione biennale"],
    ),
    "PerditaBene": PredicateSpec(
        "PerditaBene",
        ["Bene"],
        "Perdita materiale del bene consegnato al vettore (art. 1693 c.c.).",
        ["perdita della merce", "perdita bene"],
    ),
    "AvariaBene": PredicateSpec(
        "AvariaBene",
        ["Bene"],
        "Danneggiamento o avaria del bene durante il trasporto.",
        ["danneggiamento bene", "avaria della merce"],
    ),
    "PerditaAvaria": PredicateSpec(
        "PerditaAvaria",
        ["Bene"],
        "Evento unitario che copre perdita o avaria del bene trasportato.",
        ["perdita o avaria", "perditavaria"],
    ),
    "ContrattoTrasporto": PredicateSpec(
        "ContrattoTrasporto",
        ["Contratto"],
        "Contratto di trasporto disciplinato dagli artt. 1678 ss. c.c.",
        ["contratto di trasporto"],
    ),
    "EventoInadempimento": PredicateSpec(
        "EventoInadempimento",
        ["Debitore", "Contratto"],
        "Evento che rappresenta l'inadempimento del debitore.",
        ["evento inadempimento"],
    ),
    "CausaNonImputabile": PredicateSpec(
        "CausaNonImputabile",
        ["Debitore", "Contratto"],
        "Fatto liberatorio che esclude la responsabilità (caso fortuito, vizio della cosa, ecc.).",
        ["caso fortuito", "causa non imputabile"],
    ),
    "RivendicazioneProprietario": PredicateSpec(
        "RivendicazioneProprietario",
        ["Soggetto", "Bene"],
        "Azione di rivendicazione del proprietario originario contro il possessore.",
        ["rivendicazione del proprietario"],
    ),
    "IscrizioneRegistro": PredicateSpec(
        "IscrizioneRegistro",
        ["BeneRegistrato"],
        "Iscrizione del bene mobile registrato nei pubblici registri.",
        ["iscrizione registro pubblico", "iscrizione pra"],
    ),
    "NonRivendicato": PredicateSpec(
        "NonRivendicato",
        ["BeneRegistrato"],
        "Il bene mobile registrato non è oggetto di rivendicazione da parte del proprietario originario o di terzi.",
        ["nessuna rivendicazione", "nessuna_rivendicazione", "nessunarivendicazione"],
    ),
    "Riciclaggio": PredicateSpec(
        "Riciclaggio",
        ["Soggetto"],
        "Riciclaggio di proventi illeciti (art. 648-bis c.p.).",
        ["lavaggio di denaro"],
    ),
    "ContraffazioneMarchio": PredicateSpec(
        "ContraffazioneMarchio",
        ["Soggetto", "Marchio"],
        "Contraffazione o uso indebito di marchio registrato (art. 473 c.p.).",
        ["contraffazione marchio"],
    ),
    "MisuraCautelarePersonale": PredicateSpec(
        "MisuraCautelarePersonale",
        ["MisuraCautelare"],
        "Misura cautelare personale (custodia, obbligo di firma).",
        ["misura personale"],
    ),
    "MisuraCautelareReale": PredicateSpec(
        "MisuraCautelareReale",
        ["MisuraCautelare"],
        "Misura cautelare reale (sequestro, confisca).",
        ["misura reale"],
    ),
    "Multa": PredicateSpec(
        "Multa",
        ["Pena"],
        "Pena pecuniaria prevista per i delitti (art. 17 c.p.).",
        ["pena pecuniaria delitto"],
    ),
    "Ammenda": PredicateSpec(
        "Ammenda",
        ["Pena"],
        "Pena pecuniaria prevista per le contravvenzioni (art. 17 c.p.).",
        ["pena pecuniaria contravvenzione"],
    ),
    "ResponsabilitaMedicaContrattuale": PredicateSpec(
        "ResponsabilitaMedicaContrattuale",
        ["StrutturaSanitaria", "Soggetto"],
        "Responsabilità contrattuale della struttura sanitaria verso il paziente.",
        ["responsabilità medica"],
    ),
    "TrasportoResponsabilitaVettore": PredicateSpec(
        "TrasportoResponsabilitaVettore",
        ["Soggetto", "Soggetto", "Bene"],
        "Responsabilità del vettore per perdita/avaria (art. 1693 c.c.).",
        ["responsabilità vettore"],
    ),
    "SospensioneEsecuzioneForzata": PredicateSpec(
        "SospensioneEsecuzioneForzata",
        ["Procedura"],
        "Sospensione temporanea dell'esecuzione forzata (art. 624 c.p.c.).",
        ["sospensione esecuzione"],
    ),
}


def get_sort_spec(name: str) -> SortSpec:
    """Return the specification for the requested sort."""
    return SORTS[name]


def get_predicate_spec(name: str) -> PredicateSpec:
    """Return the specification for the requested predicate."""
    return PREDICATES[name]


def is_known_predicate(name: str) -> bool:
    return name in PREDICATES


def validate_predicate_signature(name: str, arity: int) -> None:
    """
    Ensure that `name` is known and that the arity matches the reference spec.
    Raises ValueError if the predicate is unknown or the arity mismatches.
    """
    spec = PREDICATES.get(name)
    if not spec:
        raise ValueError(f"Unknown predicate: {name}")
    expected = len(spec.args)
    if expected != arity:
        raise ValueError(f"Predicate '{name}' arity mismatch: expected {expected}, got {arity}")


__all__ = [
    "DSL_VERSION",
    "SORTS",
    "PREDICATES",
    "SortSpec",
    "PredicateSpec",
    "get_sort_spec",
    "get_predicate_spec",
    "is_known_predicate",
    "validate_predicate_signature",
]

