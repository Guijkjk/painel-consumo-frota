"""Testes independentes com dados inteiramente sinteticos."""
import unittest
from decimal import Decimal
from extrair_relatorio import analisar_paginas
from consultas import comparar


class PortfolioTest(unittest.TestCase):
    def pagina(self, rendimento='2,00', total='100,000 200,00 2,00'):
        return [f'Bomba: DEMO DIESEL\n01/01/2026 12:00 DEMO-A 100,000 200,00 {rendimento}\nTotal da Bomba DEMO => {total}']

    def test_extracao(self):
        registros, erros, _ = analisar_paginas(self.pagina())
        self.assertEqual(erros, [])
        self.assertEqual(registros[0]['prefixo'], 'DEMO-A')
        self.assertEqual(registros[0]['litros'], Decimal('100.000'))

    def test_total_divergente(self):
        _, erros, _ = analisar_paginas(self.pagina(total='110,000 200,00 2,00'))
        self.assertTrue(erros)

    def test_rendimento_divergente(self):
        _, erros, _ = analisar_paginas(self.pagina(rendimento='5,00'))
        self.assertTrue(erros)

    def test_comparacao(self):
        self.assertEqual(comparar(Decimal('2'), Decimal('2.5'))['situacao'], 'queda')
        self.assertEqual(comparar(Decimal('3'), Decimal('2.5'))['situacao'], 'melhora')
        self.assertEqual(comparar(Decimal('2.5'), Decimal('2.5'))['situacao'], 'estavel')
        self.assertEqual(comparar(Decimal('2'), None)['situacao'], 'sem_historico')
