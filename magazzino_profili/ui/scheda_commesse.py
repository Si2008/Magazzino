"""Commessa, verifica delle quote e lista di prelievo. Magazzino in sola lettura."""
from collections import Counter
import csv
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, QTimer
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFileDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QComboBox,
    QCheckBox, QTabWidget, QMessageBox)

from .componenti import bottone
from .richiamo_vassoi import conferma_simulazione
from ..services.consultazione import pezzo_per_barcode
from ..services.richiamo_vassoi import numero_vassoio
from ..services.commesse import RichiestaTaglio, decimi, misura, calcola_prelievo
from ..services.lettura_commessa import leggi_commessa_pdf
from ..services import archivio_commesse as archivio
from ..services import postazione, sincronizza_commesse as scambio
from ..file_sicuri import destinazione_atomica


class SchedaCommesse(QWidget):
    def __init__(self, factory, avvia_lavoro, parent=None):
        super().__init__(parent)
        self._factory, self._avvia = factory, avvia_lavoro
        self._piano = None; self._pdf = None; self._pagina = 0; self._caricamento = False
        self._documento=None;self._commessa_id=None;self._coda_ricezione=[]
        self._locale=archivio.ArchivioLocale(postazione.archivio_locale()) if factory is None else None
        layout = QVBoxLayout(self); layout.setContentsMargins(24,16,24,16); layout.setSpacing(12)
        titolo = QLabel('Commesse · prepara il prelievo', self)
        titolo.setStyleSheet('font-size:24px; font-weight:700'); layout.addWidget(titolo)
        self.stato = QLabel('Carica la lista ottimizzata PDF oppure inserisci le misure. Il magazzino non viene modificato.', self)
        self.stato.setWordWrap(True); self.stato.setTextFormat(Qt.TextFormat.PlainText); layout.addWidget(self.stato)
        scelta=QHBoxLayout();scelta.addWidget(QLabel('Commesse per cognome',self))
        self.elenco_commesse=QComboBox(self);self.elenco_commesse.setMinimumWidth(380);scelta.addWidget(self.elenco_commesse,1)
        self.apri=bottone('Apri',parent=self);scelta.addWidget(self.apri)
        self.sincronizza=bottone('Invia / verifica ricezione' if self._locale else 'Ricevi commesse',parent=self);scelta.addWidget(self.sincronizza)
        layout.addLayout(scelta);self.apri.clicked.connect(self._apri_salvata);self.sincronizza.clicked.connect(self._sincronizza)
        barra = QHBoxLayout()
        self.carica = bottone('Carica commessa PDF', icona='upload', classe='primario', parent=self)
        self.originale = bottone('Apri originale', parent=self); self.originale.setEnabled(False)
        self.aggiungi = bottone('Aggiungi misura', icona='plus', parent=self)
        self.elimina = bottone('Elimina righe', parent=self)
        for w in (self.carica,self.originale,self.aggiungi,self.elimina): barra.addWidget(w)
        barra.addStretch(); layout.addLayout(barra)
        self.carica.clicked.connect(self._carica_pdf)
        self.originale.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._pdf))))
        self.aggiungi.clicked.connect(lambda: self._aggiungi_riga())
        self.elimina.clicked.connect(self._elimina_righe)
        self.aggiungi.hide();self.elimina.hide()
        self.pagine = QTabWidget(self); layout.addWidget(self.pagine,1)
        richieste = QWidget(self); alto = QVBoxLayout(richieste); alto.setContentsMargins(0,0,0,0)
        self.tabella = QTableWidget(0,6,self)
        self.tabella.setObjectName('MisureCommessa')
        self.tabella.setStyleSheet('QTableWidget::item { padding:4px 8px; } QComboBox { padding:2px 8px; min-height:32px; } QHeaderView::section { padding:10px 8px; }')
        self.tabella.setHorizontalHeaderLabels(['Profilo originale','Colore della commessa','','Misura mm','Pezzi','Note'])
        self.tabella.setColumnHidden(2,True)
        self.tabella.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabella.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabella.verticalHeader().setDefaultSectionSize(52)
        for i,w in enumerate((145,240,300,140,100,160)): self.tabella.setColumnWidth(i,w)
        self.tabella.horizontalHeader().setStretchLastSection(True)
        alto.addWidget(self.tabella)
        self.tabella.itemChanged.connect(self._invalida)
        self.pagine.addTab(richieste,'1. Misure richieste')
        risultati = QWidget(self); basso = QVBoxLayout(risultati); basso.setContentsMargins(0,0,0,0)
        parametri = QHBoxLayout()
        self.pezzi_lunghi = QCheckBox('Usa anche pezzi più lunghi e spezzoni',self); self.pezzi_lunghi.setChecked(True)
        self.spezzoni = QCheckBox('Includi spezzoni storici',self); self.spezzoni.setChecked(True)
        self.spezzoni.setToolTip('Senza barcode proprio: vassoio da confermare. I pezzi corti con barcode sono inclusi sempre.')
        for w in (self.pezzi_lunghi,self.spezzoni): parametri.addWidget(w)
        parametri.addStretch(); alto.addLayout(parametri)
        conferma = QHBoxLayout()
        self.verifica = QCheckBox('Ho verificato misure, quantità e finiture sul documento',self)
        self.calcola = bottone('Trova pezzi e vassoi',icona='search',classe='primario',parent=self);self.calcola.setEnabled(False)
        conferma.addWidget(self.verifica,1);conferma.addWidget(self.calcola);alto.addLayout(conferma)
        self.verifica.toggled.connect(lambda v:self.calcola.setEnabled(v and self.tabella.rowCount()>0))
        self.calcola.clicked.connect(self._calcola)
        self.pezzi_lunghi.toggled.connect(self._invalida);self.spezzoni.toggled.connect(self._invalida)
        azioni = QHBoxLayout()
        self.vista = QComboBox(self);self.vista.addItems(['Da prelevare','Mancanti'])
        self.riepilogo = QLabel('Nessun piano calcolato',self)
        self.esporta = bottone('Salva lista CSV',icona='download',parent=self);self.esporta.setEnabled(False)
        self.associa=bottone('Associa pezzi alla commessa',parent=self);self.associa.setEnabled(False);self.associa.clicked.connect(self._associa)
        self.precedente = bottone('‹',parent=self);self.successiva=bottone('›',parent=self)
        for w in (self.vista,self.riepilogo,self.precedente,self.successiva,self.esporta):azioni.addWidget(w)
        basso.addLayout(azioni)
        basso.addWidget(self.associa)
        self.simula_vassoio = bottone("Simula richiamo vassoio", parent=self)
        self.simula_vassoio.setAutoDefault(False)
        self.simula_vassoio.setEnabled(False)
        self.simula_vassoio.clicked.connect(self._simula_vassoio)
        basso.addWidget(self.simula_vassoio)
        self.risultati = QTableWidget(0,6,self);self.risultati.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.risultati.setStyleSheet('QTableWidget::item { padding:4px 8px; } QHeaderView::section { padding:10px 8px; }')
        self.risultati.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.risultati.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.risultati.itemSelectionChanged.connect(self._aggiorna_simulazione)
        self.risultati.verticalHeader().setDefaultSectionSize(52)
        self.risultati.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.risultati.horizontalHeader().setStretchLastSection(True)
        basso.addWidget(self.risultati,1)
        self.avvisi = QLabel('Proposta senza prenotazione. Nessuno scarico automatico.',self)
        self.avvisi.setWordWrap(True);self.avvisi.setTextFormat(Qt.TextFormat.PlainText);basso.addWidget(self.avvisi)
        self.pagine.addTab(risultati,'2. Pezzi e vassoi')
        self.vista.currentIndexChanged.connect(self._cambia_vista)
        self.precedente.clicked.connect(lambda:self._sfoglia(-1));self.successiva.clicked.connect(lambda:self._sfoglia(1))
        self.esporta.clicked.connect(self._esporta)
        self._aggiorna_elenco()
        if self._locale:
            self.calcola.hide();self.verifica.hide();self.pezzi_lunghi.hide();self.spezzoni.hide();self.associa.hide()
            self.simula_vassoio.hide()
        self._mostra_risultati()

    def _aggiorna_elenco(self):
        try:
            corrente=self.elenco_commesse.currentData();self.elenco_commesse.clear()
            self._elenco=self._locale.elenco() if self._locale else archivio.elenco(self._factory)
            for c in sorted(self._elenco,key=lambda c:(archivio.chiave_cognome(c.cognome),c.nome)):
                identita=c.impronta if self._locale else c.identita
                self.elenco_commesse.addItem(f'{c.cognome} · {c.nome} · {identita[:8]}',identita)
            indice=self.elenco_commesse.findData(corrente)
            if indice>=0:self.elenco_commesse.setCurrentIndex(indice)
        except Exception as errore:
            self.stato.setText('Elenco commesse non leggibile: '+str(errore))

    def _apri_salvata(self):
        identita=self.elenco_commesse.currentData()
        if not identita:return
        try:
            doc=next(c for c in self._locale.elenco() if c.impronta==identita) if self._locale else archivio.carica(self._factory,identita)
            self._mostra_documento(doc,None)
        except Exception as e:QMessageBox.warning(self,'Apri commessa',str(e))

    def _importa_documento(self,doc,nome=None,accetta=False,dopo=None):
        def salva():
            try:
                return self._locale.salva(doc,accetta_omonimo=accetta) if self._locale else archivio.importa(self._factory,doc,accetta_omonimo=accetta)
            except archivio.CognomePresente as e:return str(e)
        def completato(r):
            if isinstance(r,str):
                scelta=QMessageBox.question(self,'Stesso cognome',r+'\nNessuna commessa esistente sarà sovrascritta.')
                if scelta==QMessageBox.StandardButton.Yes:
                    QTimer.singleShot(50,lambda:self._importa_documento(doc,nome,True,dopo))
                elif dopo:dopo(False)
                return
            self._aggiorna_elenco();self.elenco_commesse.setCurrentIndex(self.elenco_commesse.findData(doc.impronta))
            self._mostra_documento(doc,nome)
            if dopo:dopo(True)
        self._avvia('Salvataggio commessa',salva,completato)

    def _sincronizza(self):
        rete=postazione.impostazioni()[1]
        if self._locale:
            self._avvia('Invio commesse',lambda:scambio.invia(self._locale,rete),lambda esiti:self.avvisi.setText('\n'.join(esiti) or 'Nessuna commessa locale'))
            return
        def leggi():
            risultati=[]
            for p in scambio.da_ricevere(rete):
                try:
                    doc=archivio.leggi_file(p)
                    if doc.impronta!=p.stem:raise ValueError('Identità diversa dal nome del pacchetto: invio rifiutato')
                    risultati.append((doc,None))
                except ValueError as e:
                    try:scambio.rifiuta(rete,p.name,e)
                    except OSError as ricevuta:
                        risultati.append((None,f'Ricevuta di rifiuto non inviata: {ricevuta}'))
                    risultati.append((None,f'{p.name}: {e}'))
                except OSError as e:risultati.append((None,f'{p.name}: {e}'))
            return risultati
        def ricevuti(r):
            self._errori_ricezione=[];self._coda_ricezione=r
            self.avvisi.setText('Nessuna nuova commessa da ricevere' if not r else 'Ricezione in corso')
            QTimer.singleShot(50,self._ricevi_prossima)
        self._avvia('Lettura commesse dalla rete',leggi,ricevuti)

    def _ricevi_prossima(self):
        if not self._coda_ricezione:
            if getattr(self,'_errori_ricezione',[]):self.avvisi.setText('\n'.join(self._errori_ricezione))
            return
        doc,errore=self._coda_ricezione.pop(0)
        if errore:
            self._errori_ricezione.append(errore);self.avvisi.setText(errore);QTimer.singleShot(50,self._ricevi_prossima);return
        def dopo(accettata):
            rete=postazione.impostazioni()[1]
            def confermata(_=None):QTimer.singleShot(50,self._ricevi_prossima)
            QTimer.singleShot(50,lambda:self._avvia('Ricevuta commessa',lambda:scambio.conferma(rete,doc,'ricevuta' if accettata else 'in attesa: cognome già presente'),confermata))
        self._importa_documento(doc,dopo=dopo)

    def _associa(self):
        if not self._documento or not self._piano:return
        piano=self._piano;identita=self._documento.impronta
        self._avvia('Associazione pezzi alla commessa',lambda:archivio.assegna_piano(self._factory,identita,piano),lambda _:self.avvisi.setText('Pezzi associati alla commessa. Carico, scarico e inventario conservano il collegamento; nessun pezzo è stato scaricato.'))

    def _invalida(self,*_):
        if self._caricamento:return
        self._piano=None;self.esporta.setEnabled(False);self.verifica.setChecked(False)
        self.associa.setEnabled(False)
        self.calcola.setEnabled(False);self._pagina=0;self._mostra_risultati()

    def segnala_giacenza_cambiata(self):
        if self._piano:
            self._invalida();self.avvisi.setText('Giacenza cambiata: ricalcola il prelievo.')

    def _aggiungi_riga(self,r=None):
        if self.tabella.rowCount()>=1000:
            QMessageBox.warning(self,'Commessa','Massimo 1000 righe: suddividere la commessa');return
        n=self.tabella.rowCount();self.tabella.insertRow(n)
        for col,testo in ((0,r.profilo if r else ''),(1,r.colore if r else ''),(3,misura(r.lunghezza) if r else ''),(4,str(r.quantita) if r else '1')):
            self.tabella.setItem(n,col,QTableWidgetItem(testo))
        self.tabella.setItem(n,2,QTableWidgetItem(r.colore if r else ''))
        nota=QTableWidgetItem('Quote non lette: barra originale' if r and r.barra_intera else '')
        nota.setData(Qt.ItemDataRole.UserRole,bool(r and r.barra_intera))
        nota.setFlags(nota.flags() & ~Qt.ItemFlag.ItemIsEditable)
        nota.setToolTip(nota.text());self.tabella.setItem(n,5,nota)
        self.pagine.setCurrentIndex(0)
        self._invalida()

    def _elimina_righe(self):
        for n in sorted({i.row() for i in self.tabella.selectedIndexes()},reverse=True): self.tabella.removeRow(n)
        self._invalida()

    def _carica_pdf(self):
        nome,_=QFileDialog.getOpenFileName(self,'Carica commessa','','Commessa PDF (*.pdf)')
        if not nome:return
        self._avvia('Lettura locale della commessa',lambda:leggi_commessa_pdf(nome),lambda doc:QTimer.singleShot(50,lambda:self._importa_documento(doc,nome)))

    def _mostra_documento(self,doc,nome):
        self._documento=doc;self._caricamento=True
        self._commessa_id=next((c.id for c in self._elenco if not self._locale and c.identita==doc.impronta),None)
        try:
            self.tabella.setRowCount(0)
            for r in doc.righe:self._aggiungi_riga(r)
        finally:self._caricamento=False
        self._pdf=Path(nome) if nome else None;self.originale.setEnabled(bool(nome))
        self.pagine.setCurrentIndex(0)
        self.stato.setText(f'{doc.cognome} · {doc.nome} · {sum(r.quantita for r in doc.righe)} pezzi richiesti. Profilo e colore originali del documento.')
        self._invalida();self.avvisi.setText('\n'.join(doc.avvisi))

    def _leggi_righe(self):
        righe=[]
        for n in range(self.tabella.rowCount()):
            try:
                codice=self.tabella.item(n,0).text().strip()
                colore=self.tabella.item(n,1).text()
                lunghezza=decimi(self.tabella.item(n,3).text())
                quantita=int(self.tabella.item(n,4).text())
                righe.append(RichiestaTaglio(codice,colore,lunghezza,quantita,f'Riga {n+1}',bool(self.tabella.item(n,5).data(Qt.ItemDataRole.UserRole))))
            except (ValueError,AttributeError) as errore:
                raise ValueError(f'Riga {n+1}: {errore}') from None
        return righe

    def _calcola(self):
        try:righe=self._leggi_righe()
        except ValueError as errore:QMessageBox.warning(self,'Controlla commessa',str(errore));return
        opzioni=dict(consenti_pezzi_lunghi=self.pezzi_lunghi.isChecked(),includi_spezzoni=self.spezzoni.isChecked(),commessa_id=self._commessa_id)
        def azione():
            with self._factory() as s:return calcola_prelievo(s,righe,**opzioni)
        self._avvia('Calcolo prelievo',azione,self._ricevi_piano)

    def _ricevi_piano(self,piano):
        self._piano=piano;self._pagina=0;self.esporta.setEnabled(True)
        self.associa.setEnabled(bool(self._commessa_id and not piano.mancanti and piano.prelievi))
        self.avvisi.setText('\n'.join(piano.avvisi));self._mostra_risultati()
        self.pagine.setCurrentIndex(1)

    def _cambia_vista(self,*_):self._pagina=0;self._mostra_risultati()
    def _sfoglia(self,delta):self._pagina+=delta;self._mostra_risultati()

    @staticmethod
    def _testo_tagli(p):
        conteggi=Counter(r.lunghezza for r in p.tagli)
        return ' + '.join(f'{n} × {misura(l)}' for l,n in sorted(conteggi.items(),reverse=True))

    def _mostra_risultati(self):
        mancanti=self.vista.currentIndex()==1
        self.risultati.setHorizontalHeaderLabels(['Profilo','Colore','Misura richiesta mm','Pezzi mancanti','Motivo',''] if mancanti else ['Profilo','Colore','Misura da prendere mm','Vassoio','Barcode / riferimento','Misure della commessa mm'])
        for i in range(6):self.risultati.setColumnHidden(i,mancanti and i>=5)
        righe=(self._piano.mancanti if mancanti else self._piano.prelievi) if self._piano else []
        self._pagina=max(0,min(self._pagina,max(0,(len(righe)-1)//100)))
        selezione=righe[self._pagina*100:(self._pagina+1)*100]
        self.risultati.clearSelection()
        self.simula_vassoio.setEnabled(False)
        self.risultati.setRowCount(len(selezione))
        for n,r in enumerate(selezione):
            if mancanti:valori=(r.profilo,r.colore,misura(r.lunghezza),r.quantita,r.riferimento)
            else:
                m=r.materiale
                valori=(m.profilo,m.colore,misura(m.lunghezza),m.vassoio,m.barcode,self._testo_tagli(r))
            for col,v in enumerate(valori):
                item=QTableWidgetItem(str(v));item.setToolTip(str(v)+(('\n'+r.materiale.nota) if not mancanti and r.materiale.nota else ''));self.risultati.setItem(n,col,item)
        for i,w in enumerate((130,190,220,140,430,340)):self.risultati.setColumnWidth(i,w)
        self.precedente.setEnabled(self._pagina>0);self.successiva.setEnabled((self._pagina+1)*100<len(righe))
        if self._piano:
            self.riepilogo.setText(f'{len(self._piano.prelievi)} pezzi da prendere · {sum(r.quantita for r in self._piano.mancanti)} misure mancanti · pagina {self._pagina+1}')
        else:self.riepilogo.setText('Nessun piano aggiornato')

    def _materiale_per_simulazione(self):
        if self._factory is None or self._piano is None or self.vista.currentIndex() != 0:
            return None
        righe = self.risultati.selectionModel().selectedRows()
        if not righe:
            return None
        indice = self._pagina * 100 + righe[0].row()
        if indice >= len(self._piano.prelievi):
            return None
        materiale = self._piano.prelievi[indice].materiale
        if materiale.chiave.startswith("pezzo:") and materiale.barcode and numero_vassoio(materiale.vassoio):
            return materiale
        return None

    def _aggiorna_simulazione(self):
        self.simula_vassoio.setEnabled(self._materiale_per_simulazione() is not None)

    def _simula_vassoio(self):
        materiale = self._materiale_per_simulazione()
        if materiale is None:
            return
        vassoio = numero_vassoio(materiale.vassoio)
        with self._factory() as sessione:
            pezzo = pezzo_per_barcode(sessione, materiale.barcode)
        if (pezzo is None or materiale.chiave != f"pezzo:{pezzo.id}" or pezzo.quantita <= 0
                or numero_vassoio(pezzo.numero_vassoio) != vassoio):
            self.segnala_giacenza_cambiata()
            return

        conferma_simulazione(
            self, codice=pezzo.profilo.codice, descrizione=pezzo.profilo.descrizione,
            barcode=materiale.barcode, vassoio=vassoio, origine="commessa",
            selezione_attiva=lambda: self._materiale_per_simulazione() is materiale,
        )

    def _esporta(self):
        if not self._piano:return
        nome,_=QFileDialog.getSaveFileName(self,'Salva lista di prelievo','Prelievo_commessa.csv','CSV (*.csv)')
        if not nome:return
        piano=self._piano
        def azione():
            with destinazione_atomica(Path(nome)) as temporaneo:
                with temporaneo.open('w',encoding='utf-8-sig',newline='') as f:
                    writer=csv.writer(f,delimiter=';')
                    def scrivi(valori):writer.writerow(["'"+str(v) if str(v).startswith(('=','+','-','@','\t','\r')) else v for v in valori])
                    scrivi(['Stato','Profilo','Colore','Misura da prendere mm','Vassoio','Barcode/riferimento','Misure commessa mm','Pezzi mancanti','Note','Calcolato UTC'])
                    for p in piano.prelievi:
                        m=p.materiale;scrivi(['Da prelevare',m.profilo,m.colore,misura(m.lunghezza),m.vassoio,m.barcode,self._testo_tagli(p),'',m.nota,piano.calcolato_il])
                    for r in piano.mancanti:scrivi(['Mancante',r.profilo,r.colore,'','','',misura(r.lunghezza),r.quantita,r.riferimento,piano.calcolato_il])
                    scrivi(['Avvertenze','','','','','','','',' | '.join(piano.avvisi),piano.calcolato_il])
        self._avvia('Salvataggio lista di prelievo',azione)
