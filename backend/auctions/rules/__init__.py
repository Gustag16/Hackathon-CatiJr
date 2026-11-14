"""Regras PURAS do leilão: sem Django, sem banco, sem relógio.

Tudo aqui é função de entrada -> saída, testável em milissegundos (tests/unit).
Quem lê o relógio e o banco é a camada `auctions.services`.
"""
