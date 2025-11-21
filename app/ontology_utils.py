from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .logic_dsl import PREDICATES, SORTS, PredicateSpec, SortSpec

MANUAL_SORT_ALIASES = {
    "soggetto obbligato all'adempimento": "Debitore",
    "soggetto debitore": "Debitore",
    "soggetto titolare della pretesa": "Creditore",
    "soggetto creditore": "Creditore",
    "accordo che genera obbligazioni": "Contratto",
    "accordo tra parti che genera obbligazioni": "Contratto",
    "accordo tra parti che genera obbligazioni contrattuali": "Contratto",
    "accordo tra parti": "Contratto",
    "soggetto giuridico coinvolto nel rapporto obbligatorio": "Soggetto",
    "pregiudizio economico o non economico": "Danno",
    "pregiudizio economico": "Danno",
    "pregiudizio non economico": "Danno",
    "bene registrato": "BeneRegistrato",
    "marchio registrato": "Marchio",
    "misura cautelare personale": "MisuraCautelare",
    "misura cautelare reale": "MisuraCautelare",
    "sanzione penale": "Pena",
    "sanzione amministrativa": "Pena",
    "struttura sanitaria": "StrutturaSanitaria",
    "procedura esecutiva": "Procedura",
    "testamento olografo": "Testamento",
    "sort": "Entity",
}

MANUAL_PREDICATE_ALIASES = {
    "responsabilitacontrattuale": "ResponsabilitaContrattuale",
    "responsabilita_contrattuale": "ResponsabilitaContrattuale",
    "inadempimento": "Inadempimento",
    "mora del debitore": "Mora",
    "dannopatrimoniale": "DannoPatrimoniale",
    "ogggettononillecito": "OggettoDeterminato",
    "oggettononillecito": "OggettoDeterminato",
    "ognettodeterminato": "OggettoDeterminato",
    "causanonillecita": "CausaLegittima",
    "possessopacifico": "PossessoPubblico",
    "animusdomini": "AnimusDomini",
    "duratapossesso20anni": "DurataPossesso",
    "duratapossessoventianni": "DurataPossesso",
    "duratapossessoalmeno20anni": "DurataPossesso",
    "duratapossessoalmeno2anni": "DurataPossesso",
    "duratapossessominore2anni": "DurataPossesso",
    "duratapossessominoredueanni": "DurataPossesso",
    "perditabene": "PerditaBene",
    "avariabene": "AvariaBene",
    "perditavaria": "PerditaAvaria",
    "rivendicazioneproprietario": "RivendicazioneProprietario",
    "rivendicazione": "RivendicazioneProprietario",
    "iscrizioneregistro": "IscrizioneRegistro",
    "contrattotrasporto": "ContrattoTrasporto",
    "eventoinadempimento": "EventoInadempimento",
    "causanonimputabile": "CausaNonImputabile",
    "nonrivendicato": "NonRivendicato",
    "nessuna rivendicazione": "NonRivendicato",
    "nessuna_rivendicazione": "NonRivendicato",
    "nessunarivendicazione": "NonRivendicato",
}


def _build_sort_alias_map() -> Dict[str, str]:
    aliases: Dict[str, str] = {}
    for name, spec in SORTS.items():
        aliases[name.lower()] = name
        desc = spec.description.strip().lower()
        if desc:
            aliases[desc] = name
    aliases.update(MANUAL_SORT_ALIASES)
    return aliases


def _build_predicate_alias_map() -> Dict[str, str]:
    aliases: Dict[str, str] = {}
    for name, spec in PREDICATES.items():
        aliases[name.lower()] = name
        for synonym in spec.synonyms:
            key = synonym.strip().lower()
            if key:
                aliases[key] = name
    for key, value in MANUAL_PREDICATE_ALIASES.items():
        aliases[key.lower()] = value
    return aliases


SORT_ALIAS_MAP = _build_sort_alias_map()
PREDICATE_ALIAS_MAP = _build_predicate_alias_map()


def resolve_sort_alias(name: Optional[str], default: str = "Entity") -> str:
    if not name:
        return default
    key = str(name).strip()
    alias = SORT_ALIAS_MAP.get(key.lower())
    if alias:
        return alias
    lowered = key.lower()
    if "obbligat" in lowered:
        return "Debitore"
    if "titolare" in lowered or "creditor" in lowered:
        return "Creditore"
    if "accordo" in lowered or "contratt" in lowered:
        return "Contratto"
    return key or default


def resolve_predicate_alias(name: Optional[str]) -> str:
    if not name:
        return ""
    key = str(name).strip()
    alias = PREDICATE_ALIAS_MAP.get(key.lower())
    if alias:
        return alias
    return key


def get_predicate_signature(name: str) -> Optional[Tuple[int, List[str]]]:
    canonical = resolve_predicate_alias(name)
    spec: Optional[PredicateSpec] = PREDICATES.get(canonical)
    if not spec:
        return None
    return len(spec.args), list(spec.args)


def is_canonical_sort(name: str) -> bool:
    canonical = resolve_sort_alias(name)
    return canonical in SORTS


__all__ = [
    "resolve_sort_alias",
    "resolve_predicate_alias",
    "get_predicate_signature",
    "SORT_ALIAS_MAP",
    "PREDICATE_ALIAS_MAP",
    "is_canonical_sort",
]

