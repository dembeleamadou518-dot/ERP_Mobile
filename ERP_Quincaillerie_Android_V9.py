# -*- coding: utf-8 -*-
"""ERP QUINCAILLERIE V8 - traçabilité complète et identité visuelle, Android native Kivy.
Compatible Pydroid 3 + Kivy 2.3.1. Base SQLite locale quincaillerie.db.
"""
import os, sqlite3, shutil, csv
from datetime import date, datetime
from kivy.app import App
from kivy.metrics import dp, sp
from kivy.core.window import Window
from kivy.graphics import Color, RoundedRectangle, Line, Ellipse, Rectangle
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button as KivyButton
from kivy.uix.textinput import TextInput
from kivy.uix.spinner import Spinner
from kivy.uix.popup import Popup
from kivy.uix.widget import Widget
from kivy.uix.image import Image

# ---------------------------- Paramètres boutique
NOM_BOUTIQUE = 'QUINCAILLERIE & DIVERS DEMBELE LA 2026'
DEVISE = 'FCFA'
SEUIL_STOCK_BAS = 5
MODES = ('Espèces', 'Mobile money', 'Virement')
DOSSIER = os.path.dirname(os.path.abspath(__file__))
CHEMIN_DB = os.path.join(DOSSIER, 'quincaillerie.db')
# Place le logo fourni dans le même dossier que ce script sous le nom logo.png ou logo.jpg.
CHEMINS_LOGO = [os.path.join(DOSSIER, 'logo.png'), os.path.join(DOSSIER, 'logo.jpg'), os.path.join(DOSSIER, 'logo.jpeg')]
Window.clearcolor = (.027, .051, .094, 1)

# Palette inspirée du modèle transmis
BG = (.025, .043, .078, 1)
CARD = (.050, .078, .125, 1)
BORDER = (.105, .190, .315, 1)
TEXT = (.93, .955, .99, 1)
MUTED = (.57, .66, .79, 1)
BLUE = (.16, .43, .91, 1)
GREEN = (.06, .69, .36, 1)
RED = (.91, .23, .28, 1)
PURPLE = (.58, .31, .91, 1)
CYAN = (.12, .66, .82, 1)
GOLD = (.91, .68, .25, 1)


def connexion(chemin_db=None):
    # Réglages SQLite pour gros volumes (jusqu'à 1 million de lignes et plus).
    db = sqlite3.connect(chemin_db or CHEMIN_DB, timeout=30)
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA busy_timeout=30000')
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('PRAGMA synchronous=NORMAL')
    db.execute('PRAGMA temp_store=MEMORY')
    db.execute('PRAGMA cache_size=-20000')  # environ 20 Mo de cache SQLite
    db.execute('PRAGMA mmap_size=268435456')  # jusqu'à 256 Mo si Android le permet
    db.executescript('''    CREATE TABLE IF NOT EXISTS produits(id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT NOT NULL, prix_achat REAL DEFAULT 0, prix_vente REAL DEFAULT 0, stock INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS ventes(id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, produit_id INTEGER, quantite INTEGER, prix_unitaire REAL, prix_achat REAL);
    CREATE TABLE IF NOT EXISTS clients(id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT NOT NULL, telephone TEXT);
    CREATE TABLE IF NOT EXISTS fournisseurs(id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT NOT NULL, telephone TEXT);
    CREATE TABLE IF NOT EXISTS factures(id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, client_id INTEGER, mode TEXT, total REAL, paye REAL);
    CREATE TABLE IF NOT EXISTS entrees(id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, produit_id INTEGER, fournisseur_id INTEGER, quantite INTEGER, prix_achat REAL);
    CREATE TABLE IF NOT EXISTS caisse(id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, sens TEXT, libelle TEXT, montant REAL);
    CREATE TABLE IF NOT EXISTS mouvements_stock(id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT, date TEXT NOT NULL, produit_id INTEGER, type TEXT NOT NULL, quantite INTEGER NOT NULL, motif TEXT);
    CREATE TABLE IF NOT EXISTS paiements_clients(id INTEGER PRIMARY KEY AUTOINCREMENT, facture_id INTEGER, date TEXT, montant REAL, mode TEXT);
    CREATE TABLE IF NOT EXISTS paiements_fournisseurs(id INTEGER PRIMARY KEY AUTOINCREMENT, fournisseur_id INTEGER, date TEXT, montant REAL, mode TEXT, motif TEXT);
    CREATE TABLE IF NOT EXISTS parametres(cle TEXT PRIMARY KEY, valeur TEXT);
    ''')
    # Migration douce : ajoute les colonnes sans effacer les anciennes données.
    migrations = {
        'produits': [('reference', 'TEXT'), ('unite', "TEXT DEFAULT 'unité'"), ('categorie', "TEXT DEFAULT ''"), ('stock_min', 'INTEGER DEFAULT 5')],
        'ventes': [('facture_id', 'INTEGER')],
        'factures': [('remise', 'REAL DEFAULT 0'), ('observation', "TEXT DEFAULT ''")],
        'entrees': [('montant_total', 'REAL DEFAULT 0'), ('montant_paye', 'REAL DEFAULT 0'), ('mode_paiement', "TEXT DEFAULT 'Espèces'")],
    }
    for table, columns in migrations.items():
        existing = {r[1] for r in db.execute(f'PRAGMA table_info({table})')}
        for name, definition in columns:
            if name not in existing:
                db.execute(f'ALTER TABLE {table} ADD COLUMN {name} {definition}')
    # Identifiant métier lisible et immuable pour chaque mouvement : MVT-000000000001.
    cols = {r[1] for r in db.execute('PRAGMA table_info(mouvements_stock)')}
    if 'code' not in cols:
        db.execute('ALTER TABLE mouvements_stock ADD COLUMN code TEXT')
    db.execute("UPDATE mouvements_stock SET code='MVT-' || printf('%012d', id) WHERE code IS NULL OR code='' ")
    db.execute('CREATE UNIQUE INDEX IF NOT EXISTS ux_mouvements_code ON mouvements_stock(code)')
    db.executescript("""
        CREATE TRIGGER IF NOT EXISTS trg_mouvement_code
        AFTER INSERT ON mouvements_stock
        WHEN NEW.code IS NULL OR NEW.code=''
        BEGIN
            UPDATE mouvements_stock SET code='MVT-' || printf('%012d', NEW.id) WHERE id=NEW.id;
        END;
    """)
    # Index adaptés aux recherches, tableaux de bord et historiques volumineux.
    for sql in [
        'CREATE INDEX IF NOT EXISTS ix_mvt_id ON mouvements_stock(id DESC)',
        'CREATE INDEX IF NOT EXISTS ix_mvt_date ON mouvements_stock(date)',
        'CREATE INDEX IF NOT EXISTS ix_mvt_produit_date ON mouvements_stock(produit_id, date)',
        'CREATE INDEX IF NOT EXISTS ix_ventes_date_id ON ventes(date, id)',
        'CREATE INDEX IF NOT EXISTS ix_ventes_facture ON ventes(facture_id)',
        'CREATE INDEX IF NOT EXISTS ix_ventes_produit_date ON ventes(produit_id, date)',
        'CREATE INDEX IF NOT EXISTS ix_entrees_date_id ON entrees(date, id)',
        'CREATE INDEX IF NOT EXISTS ix_entrees_fournisseur ON entrees(fournisseur_id, id)',
        'CREATE INDEX IF NOT EXISTS ix_factures_date_id ON factures(date, id)',
        'CREATE INDEX IF NOT EXISTS ix_factures_client ON factures(client_id, id)',
        'CREATE INDEX IF NOT EXISTS ix_caisse_date_id ON caisse(date, id)',
        'CREATE INDEX IF NOT EXISTS ix_paiements_clients_facture ON paiements_clients(facture_id, date)',
        'CREATE INDEX IF NOT EXISTS ix_paiements_fournisseurs_fournisseur ON paiements_fournisseurs(fournisseur_id, date)',
        'CREATE INDEX IF NOT EXISTS ix_produits_nom ON produits(nom COLLATE NOCASE)',
        'CREATE INDEX IF NOT EXISTS ix_produits_reference ON produits(reference)',
    ]:
        db.execute(sql)
    db.executescript('''
    CREATE TABLE IF NOT EXISTS depenses(id INTEGER PRIMARY KEY AUTOINCREMENT,date TEXT NOT NULL,categorie TEXT NOT NULL,libelle TEXT NOT NULL,montant REAL NOT NULL CHECK(montant>0),mode TEXT NOT NULL,reference TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS inventaires(id INTEGER PRIMARY KEY AUTOINCREMENT,code TEXT UNIQUE,date_ouverture TEXT NOT NULL,date_cloture TEXT,statut TEXT NOT NULL DEFAULT 'OUVERT',observation TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS inventaire_lignes(id INTEGER PRIMARY KEY AUTOINCREMENT,inventaire_id INTEGER NOT NULL,produit_id INTEGER NOT NULL,stock_theorique INTEGER NOT NULL,stock_physique INTEGER,ecart INTEGER,UNIQUE(inventaire_id,produit_id),FOREIGN KEY(inventaire_id) REFERENCES inventaires(id),FOREIGN KEY(produit_id) REFERENCES produits(id));
    CREATE TABLE IF NOT EXISTS retours(id INTEGER PRIMARY KEY AUTOINCREMENT,code TEXT UNIQUE,date TEXT NOT NULL,facture_id INTEGER,produit_id INTEGER NOT NULL,quantite INTEGER NOT NULL CHECK(quantite>0),montant REAL NOT NULL DEFAULT 0,motif TEXT NOT NULL,action TEXT NOT NULL DEFAULT 'AVOIR',FOREIGN KEY(facture_id) REFERENCES factures(id),FOREIGN KEY(produit_id) REFERENCES produits(id));
    CREATE TABLE IF NOT EXISTS commandes_achat(id INTEGER PRIMARY KEY AUTOINCREMENT,code TEXT UNIQUE,date TEXT NOT NULL,fournisseur_id INTEGER,statut TEXT NOT NULL DEFAULT 'BROUILLON',total REAL NOT NULL DEFAULT 0,observation TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS clotures_caisse(id INTEGER PRIMARY KEY AUTOINCREMENT,date TEXT NOT NULL,solde_theorique REAL NOT NULL,solde_compte REAL NOT NULL,ecart REAL NOT NULL,observation TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS journal_actions(id INTEGER PRIMARY KEY AUTOINCREMENT,date TEXT NOT NULL,utilisateur TEXT NOT NULL,action TEXT NOT NULL,table_cible TEXT,ligne_id INTEGER,details TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS utilisateurs(id INTEGER PRIMARY KEY AUTOINCREMENT,nom TEXT UNIQUE NOT NULL,hash_mdp TEXT NOT NULL,role TEXT NOT NULL DEFAULT 'VENDEUR',actif INTEGER NOT NULL DEFAULT 1);
    CREATE TABLE IF NOT EXISTS sessions_inventaire(id INTEGER PRIMARY KEY AUTOINCREMENT,inventaire_id INTEGER NOT NULL,date TEXT NOT NULL,action TEXT NOT NULL,details TEXT DEFAULT '');
    CREATE TABLE IF NOT EXISTS commandes_achat_lignes(id INTEGER PRIMARY KEY AUTOINCREMENT,commande_id INTEGER NOT NULL,produit_id INTEGER NOT NULL,quantite INTEGER NOT NULL,quantite_recue INTEGER NOT NULL DEFAULT 0,prix_achat REAL NOT NULL,FOREIGN KEY(commande_id) REFERENCES commandes_achat(id),FOREIGN KEY(produit_id) REFERENCES produits(id));
    ''')
    for sql in ['CREATE INDEX IF NOT EXISTS ix_depenses_date ON depenses(date)','CREATE INDEX IF NOT EXISTS ix_retours_date ON retours(date)','CREATE INDEX IF NOT EXISTS ix_retours_facture ON retours(facture_id)','CREATE INDEX IF NOT EXISTS ix_inventaire_statut ON inventaires(statut,date_ouverture)','CREATE INDEX IF NOT EXISTS ix_audit_date ON journal_actions(date)','CREATE INDEX IF NOT EXISTS ix_commandes_fournisseur ON commandes_achat(fournisseur_id,date)']:
        db.execute(sql)
    # Journal exhaustif : les triggers SQLite enregistrent INSERT / UPDATE / DELETE,
    # même si une opération est effectuée par une fonction oubliant d'appeler audit().
    audit_cols = {r[1] for r in db.execute('PRAGMA table_info(journal_actions)')}
    for name, definition in [('evenement', "TEXT DEFAULT ''"), ('avant', 'TEXT'), ('apres', 'TEXT'), ('origine', "TEXT DEFAULT 'SQLite'")]:
        if name not in audit_cols:
            db.execute(f'ALTER TABLE journal_actions ADD COLUMN {name} {definition}')
    tables_a_suivre = ['produits','ventes','clients','fournisseurs','factures','entrees','caisse',
        'mouvements_stock','paiements_clients','paiements_fournisseurs','depenses','inventaires',
        'inventaire_lignes','retours','commandes_achat','commandes_achat_lignes','clotures_caisse','sessions_inventaire']
    for table in tables_a_suivre:
        cols_table = [r[1] for r in db.execute(f'PRAGMA table_info({table})')]
        # Exclut tout champ de mot de passe / secret si le schéma évolue.
        cols_table = [c for c in cols_table if 'mdp' not in c.lower() and 'password' not in c.lower() and 'secret' not in c.lower()]
        def obj(prefix):
            return "json_object(" + ','.join("'"+c.replace("'","''")+f"',{prefix}.{c}" for c in cols_table) + ")"
        pk = next((r[1] for r in db.execute(f'PRAGMA table_info({table})') if r[5]), 'id')
        for event in ('INSERT','UPDATE','DELETE'):
            trig = f'audit_{table}_{event.lower()}'
            before = obj('OLD') if event in ('UPDATE','DELETE') else 'NULL'
            after = obj('NEW') if event in ('INSERT','UPDATE') else 'NULL'
            rowid = f'NEW.{pk}' if event != 'DELETE' else f'OLD.{pk}'
            db.execute(f'''CREATE TRIGGER IF NOT EXISTS {trig} AFTER {event} ON {table}
                BEGIN INSERT INTO journal_actions(date,utilisateur,action,table_cible,ligne_id,details,evenement,avant,apres,origine)
                VALUES(strftime('%Y-%m-%dT%H:%M:%S','now','localtime'),'Application','{event}', '{table}', {rowid},
                'Traçabilité automatique SQLite','{event}',{before},{after},'TRIGGER SQLITE'); END''')
    # Historique des stocks déjà présents : pas de mouvement initial artificiel.
    db.commit()
    return db


def fmt(x): return f'{(x or 0):,.0f}'.replace(',', ' ')
def num(x): return float(str(x).replace(' ', '').replace('\u202f', '').replace(',', '.'))
def today(): return date.today().isoformat()
def facture_no(i): return f'F-{i:05d}'
def month_key(): return today()[:7]
def month_label():
    mois = ['janvier','février','mars','avril','mai','juin','juillet','août','septembre','octobre','novembre','décembre']
    d = date.today(); return mois[d.month-1].capitalize() + ' ' + str(d.year)
def month_shift(k):
    d = date.today(); m = d.month-k; y=d.year
    while m<=0: m+=12; y-=1
    while m>12: m-=12; y+=1
    return f'{y:04d}-{m:02d}'
def safe_float(s, default=0): return num(s) if str(s).strip() else default


class Button(KivyButton):
    """Bouton ERP homogène : fond arrondi, contraste et état pressé."""
    def __init__(self, **kwargs):
        kwargs.setdefault('background_normal', '')
        kwargs.setdefault('background_down', '')
        kwargs.setdefault('background_color', BLUE)
        kwargs.setdefault('color', TEXT)
        kwargs.setdefault('font_size', sp(14))
        kwargs.setdefault('bold', True)
        super().__init__(**kwargs)
        self.padding = (dp(12), dp(8))
        with self.canvas.before:
            self._btn_color = Color(*self.background_color)
            self._btn_rect = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(12)])
        self.bind(pos=self._draw_button, size=self._draw_button,
                  background_color=self._draw_button, state=self._draw_button)

    def _draw_button(self, *_):
        c = self.background_color
        if self.state == 'down':
            c = tuple(max(0, x * .78) for x in c[:3]) + (c[3],)
        self._btn_color.rgba = c
        self._btn_rect.pos = self.pos
        self._btn_rect.size = self.size


class Surface(BoxLayout):
    """Carte native avec fond arrondi."""
    def __init__(self, color=CARD, border=BORDER, radius=dp(18), **kwargs):
        super().__init__(**kwargs)
        self.bg_color, self.border_color, self.radius = color, border, radius
        with self.canvas.before:
            self._c = Color(*self.bg_color)
            self._r = RoundedRectangle(pos=self.pos, size=self.size, radius=[self.radius])
            self._bc = Color(*self.border_color)
            self._line = Line(rounded_rectangle=(self.x, self.y, self.width, self.height, self.radius), width=1.05)
        self.bind(pos=self._sync, size=self._sync)
    def _sync(self, *_):
        self._r.pos=self.pos; self._r.size=self.size
        self._line.rounded_rectangle=(self.x,self.y,self.width,self.height,self.radius)


class KPI(Surface):
    def __init__(self, title, value, accent=BLUE, symbol='•', **kwargs):
        super().__init__(orientation='vertical', padding=(dp(8),dp(10)), spacing=dp(3),
                         color=(.055,.10,.17,1), border=accent, **kwargs)
        self.size_hint_y=None; self.height=dp(142)
        self.add_widget(Label(text=symbol, color=accent, font_size=sp(27), size_hint_y=None, height=dp(34)))
        self.add_widget(Label(text=title, color=MUTED, font_size=sp(13), size_hint_y=None, height=dp(27)))
        self.add_widget(Label(text=str(value), color=accent, bold=True, font_size=sp(22)))


class Donut(Widget):
    def __init__(self, total=0, **kwargs):
        super().__init__(**kwargs); self.total=total
        self.bind(pos=self.draw, size=self.draw)
        self.draw()
    def draw(self, *_):
        self.canvas.clear()
        with self.canvas:
            Color(.12,.18,.29,1); Line(circle=(self.center_x,self.center_y,min(self.width,self.height)*.34), width=dp(16))
            Color(.91,.94,.98,1)
        self.canvas.ask_update()


class Bars(Widget):
    def __init__(self, values, labels, **kwargs):
        super().__init__(**kwargs); self.values=values; self.labels=labels
        self.bind(pos=self.draw, size=self.draw); self.draw()
    def draw(self, *_):
        self.canvas.clear()
        if not self.values: return
        vmax=max(max(self.values),1); n=len(self.values); gap=dp(10); usable=self.width-gap*(n+1); bw=max(dp(12),usable/n)
        with self.canvas:
            Color(.10,.16,.26,1); Line(points=[self.x,self.y+dp(24),self.right,self.y+dp(24)],width=1)
            for i,v in enumerate(self.values):
                h=max(dp(3),(self.height-dp(55))*v/vmax)
                x=self.x+gap+(bw+gap)*i
                Color(*(BLUE if i==n-1 else CYAN))
                RoundedRectangle(pos=(x,self.y+dp(25)),size=(bw,h),radius=[dp(5),dp(5),0,0])


class ERPApp(App):
    title='DEM BÉLÉ • ERP QUINCAILLERIE MOBILE'
    def build(self):
        # Android : stocker la base et le logo dans l'espace privé persistant de l'application.
        # Windows/Pydroid : conserver aussi une migration douce depuis le dossier du script.
        self.data_dir = self.user_data_dir
        os.makedirs(self.data_dir, exist_ok=True)
        self.db_path = os.path.join(self.data_dir, 'quincaillerie.db')
        if not os.path.exists(self.db_path) and os.path.isfile(CHEMIN_DB):
            try: shutil.copy2(CHEMIN_DB, self.db_path)
            except Exception: pass
        self.logo_path = os.path.join(self.data_dir, 'logo.png')
        if not os.path.exists(self.logo_path):
            for candidate in CHEMINS_LOGO:
                if os.path.isfile(candidate):
                    try: shutil.copy2(candidate, self.logo_path); break
                    except Exception: pass
        self.db=connexion(self.db_path); self.cart=[]; self.current='accueil'
        self.rootbox=BoxLayout(orientation='vertical', spacing=0, padding=0)
        # En-tête professionnel de l'application
        top=Surface(orientation='horizontal', size_hint_y=None, height=dp(72),
                    padding=(dp(16),dp(9)), spacing=dp(8),
                    color=(.045,.075,.125,1), border=(.10,.22,.37,1), radius=dp(0))
        brand=BoxLayout(orientation='horizontal', spacing=dp(10))
        logo_path=self.get_logo_path()
        if logo_path:
            brand.add_widget(Image(source=logo_path, size_hint_x=None, width=dp(54), allow_stretch=True, keep_ratio=True))
        brand_text=BoxLayout(orientation='vertical', spacing=0)
        brand_text.add_widget(Label(text='[b]DEM BÉLÉ[/b]', markup=True, color=TEXT,
                               font_size=sp(19), halign='left', valign='middle'))
        brand_text.add_widget(Label(text='GESTION • STOCK • FACTURATION', color=MUTED,
                               font_size=sp(9), halign='left', valign='top'))
        brand.add_widget(brand_text); top.add_widget(brand)
        top.add_widget(Label(text='●  LOCAL', color=GREEN, font_size=sp(10),
                             size_hint_x=None, width=dp(66), bold=True))
        self.rootbox.add_widget(top)
        # Navigation horizontale
        navscroll=ScrollView(size_hint_y=None,height=dp(55),do_scroll_y=False,bar_width=0)
        self.nav=BoxLayout(size_hint_x=None,width=dp(1600),spacing=dp(7),padding=(dp(10),dp(5)))
        self.nav_buttons={}
        tabs=[('accueil','Accueil'),('vente','Vendre'),('entrees','Entrées'),('stock','Stock'),('mouvements','Mouvements'),('produits','Produits'),('prix','Prix'),('factures','Factures'),('clients','Clients'),('fournisseurs','Fourn.'),('caisse','Caisse'),('archives','Archives'),('inventaire','Inventaire'),('achats_cmd','Cmdes achat'),('retours','Retours'),('depenses','Dépenses'),('securite','Sécurité'),('rapports','Rapports'),('sauvegarde','Sauvegarde'),('parametres','Paramètres')]
        for key,title in tabs:
            b=Button(text=title,size_hint_x=None,width=dp(112),background_normal='',background_color=(.075,.12,.20,1),color=MUTED,font_size=sp(12))
            b.bind(on_release=lambda _b,k=key:self.show(k)); self.nav.add_widget(b); self.nav_buttons[key]=b
        navscroll.add_widget(self.nav); self.rootbox.add_widget(navscroll)
        self.body=BoxLayout(orientation='vertical'); self.rootbox.add_widget(self.body)
        self.show('accueil')
        return self.rootbox

    def show(self,key):
        if key == 'vente' and self.current != 'vente': self.cart=[]
        self.current=key
        for k,b in self.nav_buttons.items():
            b.background_color=(.10,.24,.46,1) if k==key else (.07,.12,.21,1)
            b.color=TEXT if k==key else MUTED
        self.refresh()

    def get_logo_path(self):
        path = getattr(self, 'logo_path', None)
        return path if path and os.path.isfile(path) else None

    def choose_logo(self):
        """Ouvre le sélecteur de fichiers du téléphone via Plyer si disponible."""
        try:
            from plyer import filechooser
            filechooser.open_file(on_selection=self._logo_selected,
                                  filters=[('Images', '*.png', '*.jpg', '*.jpeg')])
        except Exception as exc:
            self.popup_msg("Le sélecteur de fichiers n'est pas disponible. Installe Plyer dans l'environnement de compilation Android. Détail : " + str(exc), 'Sélection du logo')

    def _logo_selected(self, selection):
        try:
            if not selection:
                return
            source = selection[0]
            if not os.path.isfile(source):
                raise ValueError("Le fichier choisi n'est pas accessible comme fichier local. Essaie de choisir une image enregistrée dans le téléphone.")
            ext = os.path.splitext(source)[1].lower()
            if ext not in ('.png', '.jpg', '.jpeg'):
                raise ValueError('Choisis une image PNG ou JPG.')
            target = os.path.join(self.data_dir, 'logo' + ('.png' if ext == '.png' else '.jpg'))
            shutil.copy2(source, target)
            # Supprime l'ancien format pour éviter qu'il soit prioritaire par erreur.
            other = os.path.join(self.data_dir, 'logo.jpg' if target.endswith('.png') else 'logo.png')
            if os.path.exists(other): os.remove(other)
            self.logo_path = target
            self.popup_msg('Ton logo est enregistré. Il apparaîtra sur l’accueil et les factures PDF.', 'Logo enregistré')
            self.show('accueil')
        except Exception as exc:
            self.popup_msg(exc, 'Erreur de logo')

    def remove_logo(self):
        try:
            for name in ('logo.png', 'logo.jpg', 'logo.jpeg'):
                path = os.path.join(self.data_dir, name)
                if os.path.isfile(path): os.remove(path)
            self.logo_path = None
            self.popup_msg('Le logo a été retiré de l’application.', 'Logo retiré')
            self.show('accueil')
        except Exception as exc:
            self.popup_msg(exc, 'Erreur')

    def popup_msg(self,msg,title='Information'):
        box=BoxLayout(orientation='vertical',padding=dp(12),spacing=dp(10))
        box.add_widget(Label(text=str(msg),color=TEXT,halign='left',valign='middle'))
        b=Button(text='Fermer',size_hint_y=None,height=dp(46),background_normal='',background_color=BLUE); box.add_widget(b)
        p=Popup(title=title,content=box,size_hint=(.9,.42),separator_color=CYAN, title_color=TEXT); b.bind(on_release=p.dismiss); p.open()

    def form_popup(self,title,fields,callback,button='Enregistrer'):
        outer=BoxLayout(orientation='vertical',padding=dp(10),spacing=dp(7))
        sc=ScrollView(); grid=GridLayout(cols=1,spacing=dp(5),size_hint_y=None); grid.bind(minimum_height=grid.setter('height')); widgets={}
        for key,label,kind,default in fields:
            grid.add_widget(Label(text=label,color=MUTED,size_hint_y=None,height=dp(25),halign='left'))
            if kind=='spinner': w=Spinner(text=default[0],values=default,size_hint_y=None,height=dp(46),background_color=(.075,.13,.21,1),color=TEXT)
            else: w=TextInput(text=str(default or ''),multiline=False,input_filter='int' if kind=='int' else None,size_hint_y=None,height=dp(46),hint_text=label,background_color=(.035,.065,.11,1),foreground_color=TEXT,cursor_color=CYAN, padding=(dp(12),dp(10)))
            widgets[key]=w; grid.add_widget(w)
        sc.add_widget(grid); outer.add_widget(sc)
        row=BoxLayout(size_hint_y=None,height=dp(48),spacing=dp(8)); cancel=Button(text='Annuler'); save=Button(text=button,background_normal='',background_color=GREEN)
        row.add_widget(cancel); row.add_widget(save); outer.add_widget(row)
        p=Popup(title=title,content=outer,size_hint=(.94,.88),separator_color=CYAN, title_color=TEXT); cancel.bind(on_release=p.dismiss)
        def submit(*_):
            values={k:w.text.strip() for k,w in widgets.items()}
            try: callback(values); p.dismiss(); self.refresh()
            except Exception as e: self.popup_msg(e,'Erreur de saisie')
        save.bind(on_release=submit); p.open()

    def refresh(self):
        self.body.clear_widgets()
        sc=ScrollView(do_scroll_x=False,bar_width=dp(3),bar_color=CYAN,bar_inactive_color=(.2,.3,.43,.35)); content=BoxLayout(orientation='vertical',padding=(dp(14),dp(14)),spacing=dp(12),size_hint_y=None)
        content.bind(minimum_height=content.setter('height')); sc.add_widget(content); self.body.add_widget(sc)
        def heading(t,sub=None):
            h=BoxLayout(orientation='vertical', size_hint_y=None, height=dp(76), spacing=dp(2))
            h.add_widget(Label(text='ESPACE DE GESTION', color=CYAN, font_size=sp(9),
                               bold=True, halign='left', valign='bottom', size_hint_y=None, height=dp(17)))
            h.add_widget(Label(text=f'[b]{t}[/b]', markup=True, color=TEXT,
                               font_size=sp(23), halign='left', valign='middle', size_hint_y=None, height=dp(34)))
            if sub:
                h.add_widget(Label(text=sub, color=MUTED, font_size=sp(11),
                                   halign='left', valign='top', size_hint_y=None, height=dp(20)))
            content.add_widget(h)
        def card(title=None, height=None):
            c=Surface(orientation='vertical',padding=(dp(15),dp(13)),spacing=dp(9),size_hint_y=None, color=(.052,.082,.135,1), border=(.105,.20,.34,1))
            c.height=dp(height or 120); c.bind(minimum_height=lambda w,h:setattr(w,'height',max(w.height,h)))
            if title: c.add_widget(Label(text=f'[b]{title}[/b]',markup=True,color=TEXT,font_size=sp(16),size_hint_y=None,height=dp(28),halign='left'))
            content.add_widget(c); return c
        def line(title,detail='',accent=MUTED):
            c=card(None,64); c.padding=(dp(12),dp(8)); c.add_widget(Label(text=f'[b]{title}[/b]'+(f'\n[size=12sp][color=8FA3BF]{detail}[/color][/size]' if detail else ''),markup=True,color=TEXT,font_size=sp(14),halign='left',valign='middle'))
        def action(title,cb,color=BLUE):
            b=Button(text=title,size_hint_y=None,height=dp(50),background_normal='',background_color=color,color=(1,1,1,1),font_size=sp(13)); b.bind(on_release=lambda *_:cb()); content.add_widget(b); return b
        db=self.db; k=self.current
        if k=='accueil':
            logo_path=self.get_logo_path()
            if logo_path:
                logo_box=Surface(orientation='vertical',size_hint_y=None,height=dp(112),padding=dp(8),radius=dp(14))
                logo_box.add_widget(Image(source=logo_path,allow_stretch=True,keep_ratio=True))
                content.add_widget(logo_box)
            heading('Vue d’ensemble',month_label()+' • Indicateurs de performance')
            _,ca_j,_=self.stats(today()); _,ca_m,benef=self.stats(month_key())
            n,stockval,bas=db.execute('SELECT COUNT(*),COALESCE(SUM(stock*prix_achat),0),COALESCE(SUM(stock<=COALESCE(stock_min,?)),0) FROM produits',(SEUIL_STOCK_BAS,)).fetchone()
            grid=GridLayout(cols=2,spacing=dp(10),size_hint_y=None); grid.bind(minimum_height=grid.setter('height'))
            for item in [('↗','Ventes du jour',fmt(ca_j),GREEN),('⚠','Stock bas',str(bas),RED),('⬡','Valeur du stock',fmt(stockval),PURPLE),('$','Bénéfice du mois',fmt(benef),BLUE)]:
                grid.add_widget(KPI(item[1],item[2],item[3],item[0]))
            content.add_widget(grid)
            # Répartition des ventes du mois
            c=card('Ventes du mois par produit',190)
            rows=db.execute("SELECT COALESCE(p.nom,'Produit supprimé'),SUM(v.quantite*v.prix_unitaire) s FROM ventes v LEFT JOIN produits p ON p.id=v.produit_id WHERE v.date LIKE ? GROUP BY v.produit_id ORDER BY s DESC LIMIT 5",(month_key()+'%',)).fetchall()
            total=sum(x[1] or 0 for x in rows)
            donutrow=BoxLayout(size_hint_y=None,height=dp(135),spacing=dp(10))
            donutrow.add_widget(Donut(total,size_hint_x=.43))
            legend=BoxLayout(orientation='vertical',spacing=dp(4))
            legend.add_widget(Label(text=f'[b]{fmt(total)}[/b]\n[size=11sp]FCFA[/size]',markup=True,color=TEXT,font_size=sp(18),size_hint_y=None,height=dp(48)))
            if rows:
                for name,val in rows[:4]: legend.add_widget(Label(text=f'{name[:20]}  {round(val/total*100) if total else 0}%',color=MUTED,font_size=sp(11),halign='left'))
            else: legend.add_widget(Label(text='Aucune vente ce mois-ci.',color=MUTED,font_size=sp(13)))
            donutrow.add_widget(legend); c.add_widget(donutrow)
            c=card('Ventes des 6 derniers mois',205)
            vals=[]; labels=[]
            short=['Jan','Fév','Mar','Avr','Mai','Juin','Juil','Août','Sep','Oct','Nov','Déc']
            for off in range(5,-1,-1):
                mk=month_shift(off); vals.append(self.stats(mk)[1]); labels.append(short[int(mk[5:7])-1])
            c.add_widget(Bars(vals,labels,size_hint_y=None,height=dp(145)))
            c.add_widget(Label(text='   '.join(labels),color=MUTED,font_size=sp(11),size_hint_y=None,height=dp(20)))
            c=card('Dernières ventes',None)
            recent=db.execute("SELECT v.date,COALESCE(p.nom,'Produit supprimé'),v.quantite,v.quantite*v.prix_unitaire FROM ventes v LEFT JOIN produits p ON p.id=v.produit_id ORDER BY v.id DESC LIMIT 5").fetchall()
            if not recent: c.add_widget(Label(text='Aucune vente pour le moment. Ouvre Vendre pour commencer.',color=MUTED,size_hint_y=None,height=dp(45)))
            for d,nm,q,m in recent: c.add_widget(Label(text=f'[b]{nm}[/b]\n[size=12sp][color=8FA3BF]{d} • Qté {q}[/color][/size]     [color=22C55E]{fmt(m)} {DEVISE}[/color]',markup=True,color=TEXT,halign='left',size_hint_y=None,height=dp(52)))
            action('＋ Nouvelle vente',lambda:self.show('vente'),GREEN)
            action('＋ Enregistrer une entrée de stock',lambda:self.show('entrees'))

        elif k=='vente':
            heading('Nouvelle vente','Ajoute les articles, puis valide pour créer la facture')
            prods=db.execute('SELECT id,nom,prix_vente,stock FROM produits WHERE stock>0 ORDER BY nom COLLATE NOCASE').fetchall()
            if not prods: line('Aucun produit en stock','Ajoute un produit ou enregistre une entrée.'); action('Ajouter un produit',lambda:self.show('produits')); return
            c=card('Ajouter un article',260)
            search_product=TextInput(hint_text='Saisir la désignation ou référence…',multiline=False,size_hint_y=None,height=dp(46),background_color=(.035,.065,.11,1),foreground_color=TEXT,cursor_color=CYAN,padding=(dp(12),dp(10)))
            spin=Spinner(text='Choisir un produit',values=[f'{i}|{n} — stock {s} — {fmt(p)}' for i,n,p,s in prods],size_hint_y=None,height=dp(46))
            selected_info=Label(text='Référence et prix affichés après sélection',color=MUTED,size_hint_y=None,height=dp(30),halign='left')
            qty=TextInput(text='1',hint_text='Quantité',input_filter='int',multiline=False,size_hint_y=None,height=dp(46),background_color=(.035,.065,.11,1),foreground_color=TEXT,cursor_color=CYAN,padding=(dp(12),dp(10)))
            c.add_widget(search_product)
            search_button=Button(text='Rechercher le produit',size_hint_y=None,height=dp(40),background_normal='',background_color=BLUE)
            c.add_widget(search_button); c.add_widget(spin); c.add_widget(selected_info); c.add_widget(qty)
            def search_for_sale(*_):
                qtxt=search_product.text.strip()
                found=db.execute("SELECT id,nom,prix_vente,stock FROM produits WHERE stock>0 AND (nom LIKE ? OR reference LIKE ?) ORDER BY nom LIMIT 40",(f'%{qtxt}%',f'%{qtxt}%')).fetchall()
                spin.values=[f'{i}|{n} — stock {st} — {fmt(pr)}' for i,n,pr,st in found]
                spin.text=spin.values[0] if spin.values else 'Aucun résultat'
                if found:
                    r=db.execute("SELECT COALESCE(reference,''),COALESCE(unite,'unité'),prix_vente FROM produits WHERE id=?",(found[0][0],)).fetchone()
                    selected_info.text=f'Réf. {r[0] or "-"} • {fmt(r[2])} FCFA / {r[1]}'
                else: selected_info.text='Aucun produit trouvé'
            search_button.bind(on_release=search_for_sale)
            def show_selected(*_):
                try:
                    pid=int(spin.text.split('|')[0]); r=db.execute("SELECT COALESCE(reference,''),COALESCE(unite,'unité'),prix_vente FROM produits WHERE id=?",(pid,)).fetchone()
                    selected_info.text=f'Réf. {r[0] or "-"} • {fmt(r[2])} FCFA / {r[1]}'
                except Exception: pass
            spin.bind(text=show_selected)
            cartlabel=Label(text='Panier vide',color=MUTED,size_hint_y=None,height=dp(52),halign='left'); c.add_widget(cartlabel)
            def add():
                try:
                    if '|' not in spin.text: raise ValueError('Choisis un produit.')
                    pid=int(spin.text.split('|')[0]); q=int(qty.text)
                    if q<=0: raise ValueError('Quantité invalide.')
                    stock=next(p[3] for p in prods if p[0]==pid); already=sum(x[1] for x in self.cart if x[0]==pid)
                    if already+q>stock: raise ValueError(f'Stock disponible : {stock}.')
                    self.cart.append((pid,q)); cartlabel.text='Panier : '+' • '.join(f'{next(p[1] for p in prods if p[0]==i)} × {n}' for i,n in self.cart)
                except Exception as e: self.popup_msg(e,'Panier')
            b=Button(text='Ajouter au panier',size_hint_y=None,height=dp(43),background_normal='',background_color=BLUE); b.bind(on_release=lambda *_:add()); c.add_widget(b)
            clients=db.execute('SELECT id,nom FROM clients ORDER BY nom').fetchall()
            fields=[('client','Client','spinner',['Client de passage']+[f'{i}|{n}' for i,n in clients]),('mode','Mode de paiement','spinner',list(MODES)),('paye','Montant payé (vide = tout)','text','')]
            # formulaire compact rendu en carte
            form=card('Informations de paiement',190)
            clientspin=Spinner(text=fields[0][3][0],values=fields[0][3],size_hint_y=None,height=dp(44)); modes=Spinner(text=MODES[0],values=MODES,size_hint_y=None,height=dp(44)); paid=TextInput(hint_text='Montant payé',multiline=False,size_hint_y=None,height=dp(44),background_color=(.035,.065,.11,1),foreground_color=TEXT,cursor_color=CYAN,padding=(dp(12),dp(10)))
            form.add_widget(clientspin); form.add_widget(modes); form.add_widget(paid)
            def validate():
                if not self.cart: raise ValueError('Ajoute au moins un article.')
                total=0; lines=[]
                for pid,q in self.cart:
                    r=db.execute('SELECT nom,prix_achat,prix_vente,stock FROM produits WHERE id=?',(pid,)).fetchone()
                    if not r or q>r[3]: raise ValueError(f'Stock insuffisant pour {r[0] if r else pid}.')
                    lines.append((pid,q,r[2] or 0,r[1] or 0)); total+=q*(r[2] or 0)
                cid=None if clientspin.text=='Client de passage' else int(clientspin.text.split('|')[0])
                pay=total if not paid.text.strip() else num(paid.text)
                if pay<0: raise ValueError('Montant payé invalide.')
                pay=min(pay,total)
                if pay<total and cid is None: raise ValueError('Choisis un client pour une vente à crédit.')
                with db:
                    cur=db.execute('INSERT INTO factures(date,client_id,mode,total,paye) VALUES(?,?,?,?,?)',(today(),cid,modes.text,total,pay)); fid=cur.lastrowid
                    for pid,q,pv,pa in lines:
                        db.execute('INSERT INTO ventes(date,produit_id,quantite,prix_unitaire,prix_achat,facture_id) VALUES(?,?,?,?,?,?)',(today(),pid,q,pv,pa,fid))
                        db.execute('UPDATE produits SET stock=stock-? WHERE id=?',(q,pid))
                        db.execute('INSERT INTO mouvements_stock(date,produit_id,type,quantite,motif) VALUES(?,?,?,?,?)',(today(),pid,'SORTIE',q,f'Vente {facture_no(fid)}'))
                    if pay:
                        db.execute('INSERT INTO paiements_clients(facture_id,date,montant,mode) VALUES(?,?,?,?)',(fid,today(),pay,modes.text))
                        db.execute('INSERT INTO caisse(date,sens,libelle,montant) VALUES(?,?,?,?)',(today(),'entree',f'Facture {facture_no(fid)} - {modes.text}',pay))
                self.cart=[]; self.popup_msg(f'Vente enregistrée\nFacture {facture_no(fid)}\nTotal : {fmt(total)} FCFA\nPayé : {fmt(pay)}\nReste : {fmt(total-pay)}'); self.show('factures')
            action('VALIDER LA VENTE',lambda:self.safe(validate),GREEN)

        elif k=='entrees':
            heading('Entrées de stock','Réception des marchandises')
            prods=db.execute('SELECT id,nom,stock,prix_achat FROM produits ORDER BY nom').fetchall(); fours=db.execute('SELECT id,nom FROM fournisseurs ORDER BY nom').fetchall()
            if not prods: line('Aucun produit','Ajoute d’abord un produit.'); action('Ajouter produit',self.add_product,GREEN); return
            def add(v):
                pid=int(v['produit'].split('|')[0]); q=int(v['quantite']); pa=num(v['prix']) if v['prix'] else None
                r=db.execute('SELECT nom,prix_achat FROM produits WHERE id=?',(pid,)).fetchone()
                if q<=0 or (pa is not None and pa<0): raise ValueError('Quantité ou prix invalide.')
                fid=int(v['fournisseur'].split('|')[0]) if v['fournisseur']!='Aucun' else None; price=pa if pa is not None else (r[1] or 0)
                total_achat=q*price; paye=num(v['paye']) if v['paye'].strip() else 0
                if paye<0 or paye>total_achat: raise ValueError(f'Montant payé invalide. Total achat : {fmt(total_achat)} FCFA.')
                with db:
                    db.execute('UPDATE produits SET stock=stock+?,prix_achat=? WHERE id=?',(q,price,pid))
                    db.execute('INSERT INTO entrees(date,produit_id,fournisseur_id,quantite,prix_achat,montant_total,montant_paye,mode_paiement) VALUES(?,?,?,?,?,?,?,?)',(today(),pid,fid,q,price,total_achat,paye,v['mode']))
                    db.execute('INSERT INTO mouvements_stock(date,produit_id,type,quantite,motif) VALUES(?,?,?,?,?)',(today(),pid,'ENTREE',q,'Réception fournisseur'))
                    if paye: db.execute('INSERT INTO caisse(date,sens,libelle,montant) VALUES(?,?,?,?)',(today(),'sortie',f'Achat {r[0]} x{q}',paye))
            fields=[('produit','Produit','spinner',[f'{i}|{n} (stock {s})' for i,n,s,pa in prods]),('fournisseur','Fournisseur','spinner',['Aucun']+[f'{i}|{n}' for i,n in fours]),('quantite','Quantité reçue','int','1'),('prix','Prix achat unitaire','text',''),('paye','Montant payé maintenant (0 si crédit)','text','0'),('mode','Mode de paiement','spinner',list(MODES))]
            action('＋ Ajouter un nouveau produit',self.add_product)
            action('＋ Enregistrer une entrée',lambda:self.form_popup('Entrée de stock',fields,add),GREEN)
            for d,n,q,pa in db.execute('SELECT e.date,p.nom,e.quantite,e.prix_achat FROM entrees e LEFT JOIN produits p ON p.id=e.produit_id ORDER BY e.id DESC LIMIT 25'):
                line(n or 'Produit supprimé',f'{d} • +{q} • {fmt(q*(pa or 0))} FCFA')

        elif k in ('stock','produits'):
            heading('État du stock' if k=='stock' else 'Catalogue produits')
            rows=db.execute("SELECT id,nom,prix_achat,prix_vente,stock,COALESCE(reference,''),COALESCE(unite,'unité'),COALESCE(stock_min,5) FROM produits ORDER BY nom").fetchall()
            if k=='produits': action('＋ Ajouter un produit',self.add_product,GREEN)
            if k=='stock': action('Voir uniquement le stock bas',lambda:self.show_low_stock(),RED)
            if not rows: line('Aucun produit enregistré.')
            for pid,n,pa,pv,stock,ref,unit,minstock in rows:
                line(n,f'{ref or "Sans référence"} • {stock} {unit} • Achat {fmt(pa)} • Vente {fmt(pv)} FCFA'+(' • STOCK BAS' if stock<=minstock else ''))
                if k=='produits': action('Modifier '+n,lambda pid=pid,n=n,pa=pa,pv=pv,ref=ref,unit=unit,minstock=minstock:self.edit_product(pid,n,pa,pv,ref,unit,minstock))

        elif k=='prix':
            heading('Consultation des prix','Recherche par désignation')
            c=card('Rechercher un produit',110)
            search=TextInput(hint_text='Saisir le nom du produit…',multiline=False,size_hint_y=None,height=dp(48),background_color=(.035,.065,.11,1),foreground_color=TEXT,cursor_color=CYAN,padding=(dp(12),dp(10)))
            c.add_widget(search)
            results=card('Résultats',None)
            def find(*_):
                results.clear_widgets(); results.add_widget(Label(text='Résultats de recherche',color=TEXT,bold=True,size_hint_y=None,height=dp(25)))
                rows=db.execute("SELECT nom,prix_vente,stock,COALESCE(reference,''),COALESCE(unite,'unité') FROM produits WHERE nom LIKE ? OR reference LIKE ? ORDER BY nom LIMIT 30",(f'%{search.text.strip()}%',f'%{search.text.strip()}%')).fetchall()
                if not rows: results.add_widget(Label(text='Aucun produit correspondant.',color=MUTED,size_hint_y=None,height=dp(40)))
                for n,p,s,ref,unit in rows: results.add_widget(Label(text=f'[b]{n}[/b]  {ref}\nPrix : {fmt(p)} FCFA     Stock : {s} {unit}',markup=True,color=TEXT,halign='left',size_hint_y=None,height=dp(55)))
            b=Button(text='Rechercher',size_hint_y=None,height=dp(45),background_normal='',background_color=BLUE); b.bind(on_release=find); c.add_widget(b)

        elif k=='factures':
            heading('Factures','Historique des ventes')
            rows=db.execute("SELECT f.id,f.date,COALESCE(c.nom,'Client de passage'),f.total,f.paye FROM factures f LEFT JOIN clients c ON c.id=f.client_id ORDER BY f.id DESC LIMIT 100").fetchall()
            if not rows: line('Aucune facture enregistrée.')
            for fid,d,cl,t,p in rows:
                action(f'{facture_no(fid)} • {cl}\n{d} • Total {fmt(t)} • Reste {fmt(t-p)} FCFA',lambda fid=fid:self.invoice_detail(fid))

        elif k in ('clients','fournisseurs'):
            isclient=k=='clients'; heading('Clients' if isclient else 'Fournisseurs')
            table='clients' if isclient else 'fournisseurs'
            action('＋ Ajouter un client' if isclient else '＋ Ajouter un fournisseur',lambda:self.add_contact('client' if isclient else 'fournisseur'),GREEN)
            rows=db.execute(f'SELECT id,nom,telephone FROM {table} ORDER BY nom').fetchall()
            for i,n,t in rows: line(n,t or 'Téléphone non renseigné')
            if not isclient:
                action('Enregistrer un règlement fournisseur',self.supplier_payment_popup,BLUE)
                debts=db.execute("SELECT f.id,f.nom,COALESCE(SUM(e.montant_total-e.montant_paye),0) FROM fournisseurs f LEFT JOIN entrees e ON e.fournisseur_id=f.id GROUP BY f.id HAVING SUM(COALESCE(e.montant_total,0)-COALESCE(e.montant_paye,0))>0 ORDER BY 3 DESC").fetchall()
                if debts:
                    c=card('Dettes fournisseurs',None)
                    for fid,n,due in debts: c.add_widget(Label(text=f'{n} • Reste dû : {fmt(due)} FCFA',color=RED,size_hint_y=None,height=dp(35),halign='left'))
            if isclient:
                debts=db.execute("SELECT c.nom, SUM(f.total-f.paye) FROM factures f JOIN clients c ON c.id=f.client_id WHERE f.total>f.paye GROUP BY c.id HAVING SUM(f.total-f.paye)>0 ORDER BY 2 DESC").fetchall()
                if debts:
                    c=card('Crédits clients',None)
                    for n,d in debts: c.add_widget(Label(text=f'{n} • Reste dû : {fmt(d)} FCFA',color=RED,size_hint_y=None,height=dp(35),halign='left'))

        elif k=='caisse':
            heading('Caisse','Entrées et sorties financières')
            solde=db.execute("SELECT COALESCE(SUM(CASE WHEN sens='entree' THEN montant ELSE -montant END),0) FROM caisse").fetchone()[0]
            c=card('Solde actuel',85); c.add_widget(Label(text=f'[b]{fmt(solde)} FCFA[/b]',markup=True,color=GREEN if solde>=0 else RED,font_size=sp(23)))
            action('＋ Nouveau mouvement',self.add_cash,GREEN)
            for d,s,l,m in db.execute('SELECT date,sens,libelle,montant FROM caisse ORDER BY id DESC LIMIT 60'):
                line(l,f'{d} • {"+" if s=="entree" else "−"}{fmt(m)} FCFA',GREEN if s=='entree' else RED)

        elif k=='rapports':
            heading('Rapports de gestion','Indicateurs calculés à partir des opérations enregistrées')
            m=month_key(); ventes,ca,benef=self.stats(m)
            achats=db.execute("SELECT COALESCE(SUM(montant_total),0),COALESCE(SUM(montant_paye),0) FROM entrees WHERE date LIKE ?",(m+'%',)).fetchone()
            credits=db.execute('SELECT COALESCE(SUM(total-paye),0) FROM factures').fetchone()[0]
            dettes_fournisseurs=db.execute('SELECT COALESCE(SUM(montant_total-montant_paye),0) FROM entrees').fetchone()[0]
            c=card('Synthèse du mois',None)
            for label,value in [('Nombre de lignes vendues',ventes),('Chiffre d’affaires',fmt(ca)+' FCFA'),('Marge brute estimée',fmt(benef)+' FCFA'),('Achats enregistrés',fmt(achats[0])+' FCFA'),('Achats payés',fmt(achats[1])+' FCFA'),('Crédits clients restants',fmt(credits)+' FCFA'),('Dettes fournisseurs restantes',fmt(dettes_fournisseurs)+' FCFA')]:
                c.add_widget(Label(text=f'{label} : {value}',color=TEXT,size_hint_y=None,height=dp(32),halign='left'))
            action('Exporter les ventes en CSV',self.export_sales_csv)
            action('Exporter le catalogue en CSV',self.export_products_csv)
            action('Exporter les mouvements de stock en CSV',self.export_stock_csv)

        elif k=='parametres':
            heading('Paramètres de l’application','Personnalise ton ERP directement depuis le téléphone')
            action('Choisir / remplacer mon logo',self.choose_logo,GREEN)
            action('Retirer le logo',self.remove_logo,RED)
            line('Emplacement des données','Base et logo conservés dans le stockage privé de l’application.')
            line('Fonctionnement','Application locale : aucune connexion Internet obligatoire.')
            action('Créer une sauvegarde maintenant',self.backup_database,BLUE)

        elif k=='sauvegarde':
            heading('Sauvegarde et sécurité','Base SQLite optimisée • identifiants de mouvements • gros historiques')
            line('Base de données',self.db_path)
            line('Conseil','Faire une sauvegarde avant toute mise à jour ou suppression.')
            action('Créer une sauvegarde maintenant',self.backup_database,GREEN)
            action('Voir les mouvements de stock',lambda:self.show('mouvements'))

        elif k=='mouvements':
            heading('Mouvements de stock','Historique des entrées et sorties')
            rows=db.execute("SELECT m.code,m.date,COALESCE(p.nom,'Produit supprimé'),m.type,m.quantite,m.motif FROM mouvements_stock m LEFT JOIN produits p ON p.id=m.produit_id ORDER BY m.id DESC LIMIT 200").fetchall()
            if not rows: line('Aucun mouvement enregistré.')
            for code,d,n,t,q,motif in rows: line(f'{code} • {n}',f'{d} • {t} {q} • {motif or ""}')


        elif k=='achats_cmd':
            heading('Commandes fournisseurs','Préparer les achats, suivre les reliquats et réceptionner partiellement')
            action('＋ Créer une commande fournisseur',self.create_purchase_order,GREEN)
            rows=db.execute('''SELECT c.id,c.code,c.date,COALESCE(f.nom,'Fournisseur'),c.statut,
                COALESCE(SUM((l.quantite-l.quantite_recue)*l.prix_achat),0),COUNT(l.id)
                FROM commandes_achat c LEFT JOIN fournisseurs f ON f.id=c.fournisseur_id
                LEFT JOIN commandes_achat_lignes l ON l.commande_id=c.id
                GROUP BY c.id ORDER BY c.id DESC LIMIT 100''').fetchall()
            if not rows: line('Aucune commande fournisseur.')
            for oid,code,d,supplier,status,remaining,count in rows:
                line(f'{code} • {supplier}',f'{d} • {status} • Reliquat estimé : {fmt(remaining)} FCFA • {count} ligne(s)')
                if status not in ('RECUE','ANNULEE'):
                    action('Réceptionner cette commande',lambda oid=oid:self.receive_purchase_order(oid),BLUE)

        elif k=='inventaire':
            heading('Inventaire physique','Comptage réel, écarts et ajustements traçables')
            opened=db.execute("SELECT id,code,date_ouverture FROM inventaires WHERE statut='OUVERT' ORDER BY id DESC LIMIT 1").fetchone()
            if opened:
                iid,icode,od=opened
                line('Inventaire ouvert : '+str(icode),'Démarré le '+str(od))
                action('Saisir un comptage physique',lambda:self.inventory_count_popup(iid),BLUE)
                action('Clôturer et appliquer les écarts',lambda:self.close_inventory(iid),GREEN)
            else: action('＋ Démarrer un inventaire',self.start_inventory,GREEN)
            rows=db.execute("SELECT i.code,i.date_ouverture,i.statut,COUNT(l.id) FROM inventaires i LEFT JOIN inventaire_lignes l ON l.inventaire_id=i.id GROUP BY i.id ORDER BY i.id DESC LIMIT 30").fetchall()
            c=card('Historique des inventaires',None)
            for r in rows: c.add_widget(Label(text=f'{r[0]} • {r[1]} • {r[2]} • {r[3]} lignes',color=TEXT,size_hint_y=None,height=dp(35)))
            if not rows: c.add_widget(Label(text='Aucun inventaire.',color=MUTED,size_hint_y=None,height=dp(35)))

        elif k=='retours':
            heading('Retours clients','Tracer les retours et réintégrer les produits acceptés')
            action('＋ Enregistrer un retour',self.return_popup,GREEN)
            rows=db.execute("SELECT r.code,r.date,p.nom,r.quantite,r.montant,r.motif,r.action FROM retours r LEFT JOIN produits p ON p.id=r.produit_id ORDER BY r.id DESC LIMIT 100").fetchall()
            c=card('Historique des retours',None)
            for r in rows: c.add_widget(Label(text=f'{r[0]} • {r[1]} • {r[2]} × {r[3]} • {fmt(r[4])} FCFA\n{r[5]} • {r[6]}',color=TEXT,size_hint_y=None,height=dp(52)))
            if not rows: c.add_widget(Label(text='Aucun retour enregistré.',color=MUTED,size_hint_y=None,height=dp(35)))

        elif k=='depenses':
            heading('Dépenses et charges','Charges d’exploitation et impact sur la caisse')
            action('＋ Enregistrer une dépense',self.expense_popup,GREEN)
            total=db.execute("SELECT COALESCE(SUM(montant),0) FROM depenses WHERE date LIKE ?",(month_key()+'%',)).fetchone()[0]
            c=card('Dépenses du mois',75); c.add_widget(Label(text=fmt(total)+' FCFA',color=GOLD,font_size=sp(22),bold=True))
            rows=db.execute('SELECT date,categorie,libelle,montant,mode FROM depenses ORDER BY id DESC LIMIT 100').fetchall()
            c=card('Historique des dépenses',None)
            for r in rows: c.add_widget(Label(text=f'{r[0]} • {r[1]} • {r[2]}\n{fmt(r[3])} FCFA • {r[4]}',color=TEXT,size_hint_y=None,height=dp(52)))
            if not rows: c.add_widget(Label(text='Aucune dépense enregistrée.',color=MUTED,size_hint_y=None,height=dp(35)))

        elif k=='securite':
            heading('Contrôle et traçabilité','Diagnostic SQLite, journal des actions et clôture de caisse')
            action('Vérifier l’intégrité de la base',self.check_integrity,GREEN)
            action('Clôturer la caisse du jour',self.cash_closure_popup,PURPLE)
            action('Exporter le journal des actions',self.export_audit_csv,BLUE)
            rows=db.execute('SELECT date,utilisateur,action,table_cible,ligne_id,evenement,details FROM journal_actions ORDER BY id DESC LIMIT 100').fetchall()
            c=card('Journal des actions',None)
            for r in rows: c.add_widget(Label(text=f'{r[0]} • {r[1]} • {r[2]} {r[5] or ""} • {r[3] or ""} #{r[4] or ""}\n{r[6] or ""}',color=TEXT,size_hint_y=None,height=dp(52)))
            if not rows: c.add_widget(Label(text='Les créations, modifications et suppressions des tables métier sont journalisées automatiquement.',color=MUTED,size_hint_y=None,height=dp(40)))

        elif k=='archives':
            heading('Archives','Synthèse mensuelle')
            rows=db.execute('SELECT substr(date,1,7),COUNT(*),COALESCE(SUM(total),0),COALESCE(SUM(paye),0) FROM factures GROUP BY substr(date,1,7) ORDER BY 1 DESC').fetchall()
            if not rows: line('Aucune archive disponible.')
            for m,n,t,p in rows: line(m,f'{n} facture(s) • Ventes {fmt(t)} • Encaissé {fmt(p)} FCFA')

    def stats(self,prefix):
        return self.db.execute('SELECT COUNT(*),COALESCE(SUM(quantite*prix_unitaire),0),COALESCE(SUM(quantite*(prix_unitaire-prix_achat)),0) FROM ventes WHERE date LIKE ?',(prefix+'%',)).fetchone()
    def safe(self,fn):
        try: fn()
        except Exception as e: self.popup_msg(e,'Erreur')
    def add_product(self):
        def save(v):
            pa,pv=num(v['achat']),num(v['vente']); stock=int(v['stock'] or 0); minimum=int(v['minimum'] or SEUIL_STOCK_BAS)
            if not v['nom'] or min(pa,pv,stock,minimum)<0: raise ValueError('Nom, prix, stock ou seuil invalide.')
            ref=v['reference'].strip()
            if ref and self.db.execute('SELECT 1 FROM produits WHERE reference=?',(ref,)).fetchone(): raise ValueError('Cette référence existe déjà.')
            with self.db:
                cur=self.db.execute('INSERT INTO produits(nom,prix_achat,prix_vente,stock,reference,unite,categorie,stock_min) VALUES(?,?,?,?,?,?,?,?)',(v['nom'],pa,pv,stock,ref,v['unite'] or 'unité',v['categorie'],minimum))
                if stock: self.db.execute('INSERT INTO mouvements_stock(date,produit_id,type,quantite,motif) VALUES(?,?,?,?,?)',(today(),cur.lastrowid,'ENTREE',stock,'Stock initial'))
        self.form_popup('Ajouter un produit',[('reference','Référence','text',''),('nom','Désignation','text',''),('unite','Unité (pièce, sac, mètre...)','text','unité'),('categorie','Catégorie','text',''),('achat','Prix d’achat','text','0'),('vente','Prix de vente','text','0'),('stock','Stock initial','int','0'),('minimum','Seuil d’alerte stock','int',str(SEUIL_STOCK_BAS))],save)
    def edit_product(self,pid,n,pa,pv,ref='',unit='unité',minimum=5):
        def save(v):
            a,b=num(v['achat']),num(v['vente']); mi=int(v['minimum'] or SEUIL_STOCK_BAS)
            if not v['nom'] or min(a,b,mi)<0: raise ValueError('Informations invalides.')
            if v['reference'] and self.db.execute('SELECT 1 FROM produits WHERE reference=? AND id<>?',(v['reference'],pid)).fetchone(): raise ValueError('Référence déjà utilisée.')
            with self.db: self.db.execute('UPDATE produits SET reference=?,nom=?,unite=?,prix_achat=?,prix_vente=?,stock_min=? WHERE id=?',(v['reference'],v['nom'],v['unite'],a,b,mi,pid))
        self.form_popup('Modifier le produit',[('reference','Référence','text',ref),('nom','Désignation','text',n),('unite','Unité','text',unit),('achat','Prix d’achat','text',pa),('vente','Prix de vente','text',pv),('minimum','Seuil stock bas','int',str(minimum))],save)
    def show_low_stock(self):
        rows=self.db.execute("SELECT nom,stock,COALESCE(stock_min,5),COALESCE(unite,'unité') FROM produits WHERE stock<=COALESCE(stock_min,5) ORDER BY stock").fetchall()
        self.list_popup('Alertes de stock bas',[f'{n} : {s} {u} (seuil {m})' for n,s,m,u in rows] or ['Aucun stock bas.'])
    def list_popup(self,title,items):
        box=BoxLayout(orientation='vertical',padding=dp(10),spacing=dp(7)); sc=ScrollView(); grid=GridLayout(cols=1,size_hint_y=None,spacing=dp(6)); grid.bind(minimum_height=grid.setter('height'))
        for item in items: grid.add_widget(Label(text=item,color=TEXT,size_hint_y=None,height=dp(42),halign='left'))
        sc.add_widget(grid); box.add_widget(sc); b=Button(text='Fermer',size_hint_y=None,height=dp(45)); box.add_widget(b); pop=Popup(title=title,content=box,size_hint=(.92,.75)); b.bind(on_release=pop.dismiss); pop.open()
    def backup_database(self):
        try:
            folder=os.path.join(self.data_dir,'Sauvegardes'); os.makedirs(folder,exist_ok=True)
            target=os.path.join(folder,'quincaillerie_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.db')
            # API backup SQLite : inclut correctement les données encore dans le WAL.
            dest=sqlite3.connect(target)
            try: self.db.backup(dest, pages=200)
            finally: dest.close()
            self.popup_msg('Sauvegarde créée :\n'+target,'Sauvegarde réussie')
        except Exception as e: self.popup_msg(e,'Erreur de sauvegarde')
    def _export_rows(self,filename,headers,rows):
        folder=os.path.join(self.data_dir,'Exports'); os.makedirs(folder,exist_ok=True); target=os.path.join(folder,filename)
        with open(target,'w',newline='',encoding='utf-8-sig') as f:
            w=csv.writer(f,delimiter=';'); w.writerow(headers)
            # Écriture progressive : évite de charger 1 000 000 de lignes en mémoire.
            for row in rows: w.writerow(row)
        self.popup_msg('Fichier créé :\n'+target,'Export terminé')
    def export_sales_csv(self):
        rows=self.db.execute("SELECT f.date,'F-'||printf('%05d',f.id),COALESCE(c.nom,'Client de passage'),f.total,f.paye,(f.total-f.paye),f.mode FROM factures f LEFT JOIN clients c ON c.id=f.client_id ORDER BY f.id DESC")
        self._export_rows('ventes.csv',['Date','Facture','Client','Total','Payé','Reste','Mode'],rows)
    def export_products_csv(self):
        rows=self.db.execute('SELECT reference,nom,unite,categorie,prix_achat,prix_vente,stock,stock_min FROM produits ORDER BY nom')
        self._export_rows('produits.csv',['Référence','Désignation','Unité','Catégorie','Prix achat','Prix vente','Stock','Seuil'],rows)
    def export_stock_csv(self):
        rows=self.db.execute("SELECT m.code,m.date,COALESCE(p.reference,''),COALESCE(p.nom,''),m.type,m.quantite,m.motif FROM mouvements_stock m LEFT JOIN produits p ON p.id=m.produit_id ORDER BY m.id DESC")
        self._export_rows('mouvements_stock.csv',['ID mouvement','Date','Référence','Produit','Type','Quantité','Motif'],rows)
    def add_contact(self,kind):
        table='clients' if kind=='client' else 'fournisseurs'
        def save(v):
            if not v['nom']: raise ValueError('Le nom est obligatoire.')
            with self.db: self.db.execute(f'INSERT INTO {table}(nom,telephone) VALUES(?,?)',(v['nom'],v['tel']))
        self.form_popup('Ajouter '+kind,[('nom','Nom','text',''),('tel','Téléphone','text','')],save)
    def supplier_payment_popup(self):
        suppliers=self.db.execute("SELECT id,nom FROM fournisseurs ORDER BY nom").fetchall()
        if not suppliers: return self.popup_msg('Ajoute d’abord un fournisseur.')
        opts=[f'{i}|{n}' for i,n in suppliers]
        def save(v):
            fid=int(v['fournisseur'].split('|')[0]); amount=num(v['montant']); mode=v['mode']
            if amount<=0: raise ValueError('Le montant doit être positif.')
            due=self.db.execute('SELECT COALESCE(SUM(montant_total-montant_paye),0) FROM entrees WHERE fournisseur_id=?',(fid,)).fetchone()[0]
            if amount>due+0.009: raise ValueError(f'Dette restante : {fmt(due)} FCFA.')
            left=amount
            with self.db:
                bills=self.db.execute('SELECT id,montant_total,montant_paye FROM entrees WHERE fournisseur_id=? AND montant_total>montant_paye ORDER BY id',(fid,)).fetchall()
                for eid,total,paid in bills:
                    part=min(left,total-paid)
                    if part>0:
                        self.db.execute('UPDATE entrees SET montant_paye=montant_paye+? WHERE id=?',(part,eid)); left-=part
                    if left<=0.009: break
                self.db.execute('INSERT INTO paiements_fournisseurs(fournisseur_id,date,montant,mode,motif) VALUES(?,?,?,?,?)',(fid,today(),amount,mode,v['motif']))
                name=next(n for i,n in suppliers if i==fid)
                self.db.execute('INSERT INTO caisse(date,sens,libelle,montant) VALUES(?,?,?,?)',(today(),'sortie',f'Règlement fournisseur {name} - {mode}',amount))
        self.form_popup('Règlement fournisseur',[('fournisseur','Fournisseur','spinner',opts),('montant','Montant réglé','text',''),('mode','Mode de paiement','spinner',list(MODES)),('motif','Motif / référence','text','')],save)
    def add_cash(self):
        def save(v):
            m=num(v['montant'])
            if m<=0 or not v['libelle']: raise ValueError('Libellé et montant positif obligatoires.')
            with self.db: self.db.execute('INSERT INTO caisse(date,sens,libelle,montant) VALUES(?,?,?,?)',(today(),v['sens'],v['libelle'],m))
        self.form_popup('Mouvement de caisse',[('sens','Type','spinner',['entree','sortie']),('libelle','Libellé','text',''),('montant','Montant','text','')],save)
    def invoice_detail(self,fid):
        f=self.db.execute("SELECT f.date,COALESCE(c.nom,'Client de passage'),f.mode,f.total,f.paye FROM factures f LEFT JOIN clients c ON c.id=f.client_id WHERE f.id=?",(fid,)).fetchone()
        if not f: return self.popup_msg('Facture introuvable.')
        d,c,mode,total,paid=f; rows=self.db.execute("SELECT COALESCE(p.nom,'Produit supprimé'),v.quantite,v.prix_unitaire,COALESCE(p.reference,''),COALESCE(p.unite,'unité') FROM ventes v LEFT JOIN produits p ON p.id=v.produit_id WHERE v.facture_id=?",(fid,)).fetchall()
        text=f'{NOM_BOUTIQUE}\nFACTURE {facture_no(fid)}\nDate : {d}\nClient : {c}\nPaiement : {mode}\n\n'+'\n'.join(f'{n} [{ref}] | {q} {unit} x {fmt(p)} = {fmt(q*p)}' for n,q,p,ref,unit in rows)+f'\n\nTOTAL : {fmt(total)} {DEVISE}\nPAYÉ : {fmt(paid)} {DEVISE}\nRESTE : {fmt(max(0,total-paid))} {DEVISE}'
        box=BoxLayout(orientation='vertical',padding=dp(10),spacing=dp(8)); ti=TextInput(text=text,readonly=True,foreground_color=TEXT,background_color=(.04,.08,.14,1)); box.add_widget(ti)
        pdf=Button(text='Exporter la facture en PDF',size_hint_y=None,height=dp(46)); box.add_widget(pdf); pdf.bind(on_release=lambda *_:self.export_invoice_pdf(fid))
        if total-paid>0.009:
            b=Button(text='Enregistrer un paiement',size_hint_y=None,height=dp(46)); box.add_widget(b); b.bind(on_release=lambda *_:(self.payment_popup(fid,total-paid),pop.dismiss()))
        close=Button(text='Fermer',size_hint_y=None,height=dp(44)); box.add_widget(close)
        pop=Popup(title=f'Facture {facture_no(fid)}',content=box,size_hint=(.95,.85),separator_color=BLUE); close.bind(on_release=pop.dismiss); pop.open()
    def payment_popup(self,fid,reste):
        def save(v):
            m=num(v['montant']); mode=v['mode']; r=self.db.execute('SELECT total,paye FROM factures WHERE id=?',(fid,)).fetchone()
            if m<=0 or m>r[0]-r[1]+.009: raise ValueError('Montant de paiement invalide.')
            with self.db:
                self.db.execute('UPDATE factures SET paye=paye+? WHERE id=?',(m,fid))
                self.db.execute('INSERT INTO paiements_clients(facture_id,date,montant,mode) VALUES(?,?,?,?)',(fid,today(),m,mode))
                self.db.execute('INSERT INTO caisse(date,sens,libelle,montant) VALUES(?,?,?,?)',(today(),'entree',f'Paiement facture {facture_no(fid)} - {mode}',m))
        self.form_popup('Paiement facture',[('montant','Montant reçu','text',fmt(reste)),('mode','Mode de paiement','spinner',list(MODES))],save)
    def export_invoice_pdf(self,fid):
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.pdfgen import canvas
            from reportlab.lib import colors
            folder=os.path.join(self.data_dir,'FacturesPDF'); os.makedirs(folder,exist_ok=True)
            target=os.path.join(folder,f'Facture_{facture_no(fid)}.pdf')
            f=self.db.execute("SELECT f.date,COALESCE(c.nom,'Client de passage'),f.mode,f.total,f.paye FROM factures f LEFT JOIN clients c ON c.id=f.client_id WHERE f.id=?",(fid,)).fetchone()
            lines=self.db.execute("SELECT COALESCE(p.nom,'Produit supprimé'),v.quantite,v.prix_unitaire,COALESCE(p.reference,''),COALESCE(p.unite,'unité') FROM ventes v LEFT JOIN produits p ON p.id=v.produit_id WHERE v.facture_id=?",(fid,)).fetchall()
            c=canvas.Canvas(target,pagesize=A4); w,h=A4; y=h-48
            logo_path=self.get_logo_path()
            if logo_path:
                try:
                    from reportlab.lib.utils import ImageReader
                    img=ImageReader(logo_path); iw,ih=img.getSize(); scale=min(105/max(iw,1),65/max(ih,1))
                    c.drawImage(img,(w-iw*scale)/2,y-ih*scale,width=iw*scale,height=ih*scale, preserveAspectRatio=True,mask='auto')
                    y-=ih*scale+12
                except Exception: pass
            c.setFillColor(colors.HexColor('#10233D')); c.setFont('Helvetica-Bold',17); c.drawCentredString(w/2,y,NOM_BOUTIQUE[:55]); y-=28
            c.setFont('Helvetica-Bold',14); c.drawCentredString(w/2,y,'FACTURE '+facture_no(fid)); y-=24
            c.setFont('Helvetica',10)
            for label,value in [('Date',f[0]),('Client',f[1]),('Paiement',f[2])]: c.drawCentredString(w/2,y,f'{label} : {value}'); y-=17
            y-=10; c.setFont('Helvetica-Bold',9)
            c.drawCentredString(145,y,'Désignation'); c.drawCentredString(300,y,'Qté'); c.drawCentredString(390,y,'Prix unit.'); c.drawCentredString(500,y,'Montant'); y-=15
            c.line(42,y,w-42,y); y-=18; c.setFont('Helvetica',9)
            for n,q,pv,ref,unit in lines:
                if y<90: c.showPage(); y=h-55; c.setFont('Helvetica',9)
                c.drawCentredString(145,y,(n+' '+('('+ref+')' if ref else ''))[:42]); c.drawCentredString(300,y,f'{q} {unit}'); c.drawCentredString(390,y,fmt(pv)); c.drawCentredString(500,y,fmt(q*pv)); y-=18
            y-=15; c.setFont('Helvetica-Bold',11); c.drawCentredString(w/2,y,'TOTAL : '+fmt(f[3])+' FCFA'); y-=20
            c.setFont('Helvetica',10); c.drawCentredString(w/2,y,'Payé : '+fmt(f[4])+' FCFA'); y-=18; c.drawCentredString(w/2,y,'Reste : '+fmt(max(0,f[3]-f[4]))+' FCFA')
            c.save(); self.popup_msg('PDF enregistré :\n'+target,'Facture exportée')
        except ImportError:
            self.popup_msg('Le module reportlab n’est pas installé. Installe reportlab dans Pip pour activer l’export PDF. Les factures restent consultables dans l’application.','Module PDF absent')
        except Exception as e: self.popup_msg(e,'Erreur PDF')

    def create_purchase_order(self):
        suppliers=self.db.execute('SELECT id,nom FROM fournisseurs ORDER BY nom').fetchall()
        products=self.db.execute('SELECT id,nom,prix_achat FROM produits ORDER BY nom').fetchall()
        if not suppliers: return self.popup_msg('Ajoute d’abord un fournisseur.')
        if not products: return self.popup_msg('Ajoute d’abord des produits au catalogue.')
        def save(v):
            sid=int(v['fournisseur'].split('|')[0]); pid=int(v['produit'].split('|')[0])
            qty=int(v['quantite']); price=num(v['prix'])
            if qty<=0 or price<0: raise ValueError('Quantité ou prix invalide.')
            code='ACH-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')
            with self.db:
                cur=self.db.execute("INSERT INTO commandes_achat(code,date,fournisseur_id,statut,total,observation) VALUES(?,?,?,'EN_COURS',?,?)",(code,today(),sid,qty*price,v['observation']))
                self.db.execute('INSERT INTO commandes_achat_lignes(commande_id,produit_id,quantite,prix_achat) VALUES(?,?,?,?)',(cur.lastrowid,pid,qty,price))
            self.audit('CREATION COMMANDE ACHAT','commandes_achat',cur.lastrowid,code)
        self.form_popup('Nouvelle commande fournisseur',[('fournisseur','Fournisseur','spinner',[f'{i}|{n}' for i,n in suppliers]),('produit','Produit','spinner',[f'{i}|{n}' for i,n,_ in products]),('quantite','Quantité commandée','int','1'),('prix','Prix d’achat unitaire FCFA','text','0'),('observation','Observation','text','')],save)

    def receive_purchase_order(self, order_id):
        order=self.db.execute("SELECT id,code,fournisseur_id,statut FROM commandes_achat WHERE id=?",(order_id,)).fetchone()
        if not order: return self.popup_msg('Commande introuvable.')
        if order[3] in ('RECUE','ANNULEE'): return self.popup_msg('Cette commande est déjà terminée.')
        lines=self.db.execute('SELECT l.id,p.nom,l.quantite,l.quantite_recue,l.prix_achat,p.id FROM commandes_achat_lignes l JOIN produits p ON p.id=l.produit_id WHERE l.commande_id=?',(order_id,)).fetchall()
        if not lines: return self.popup_msg('La commande ne contient aucune ligne.')
        opts=[f'{r[0]}|{r[1]} (reste {r[2]-r[3]})' for r in lines if r[2]>r[3]]
        if not opts: return self.popup_msg('Aucun reliquat à réceptionner.')
        def save(v):
            lid=int(v['ligne'].split('|')[0]); line=self.db.execute('SELECT produit_id,quantite,quantite_recue,prix_achat FROM commandes_achat_lignes WHERE id=?',(lid,)).fetchone()
            qty=int(v['quantite']); remaining=line[1]-line[2]
            if qty<=0 or qty>remaining: raise ValueError(f'Quantité reçue invalide. Reste à recevoir : {remaining}.')
            total=qty*line[3]; paid=num(v['paye'])
            if paid<0 or paid>total: raise ValueError('Le montant payé doit être compris entre 0 et le total reçu.')
            with self.db:
                self.db.execute('UPDATE commandes_achat_lignes SET quantite_recue=quantite_recue+? WHERE id=?',(qty,lid))
                self.db.execute('UPDATE produits SET stock=stock+?,prix_achat=? WHERE id=?',(qty,line[3],line[0]))
                self.db.execute('INSERT INTO entrees(date,produit_id,fournisseur_id,quantite,prix_achat,montant_total,montant_paye,mode_paiement) VALUES(?,?,?,?,?,?,?,?)',(today(),line[0],order[2],qty,line[3],total,paid,v['mode']))
                self.db.execute('INSERT INTO mouvements_stock(date,produit_id,type,quantite,motif) VALUES(?,?,?,?,?)',(today(),line[0],'ENTREE',qty,'Réception '+order[1]))
                if paid:
                    self.db.execute('INSERT INTO caisse(date,sens,libelle,montant) VALUES(?,?,?,?)',(today(),'sortie','Paiement réception '+order[1],paid))
                left=self.db.execute('SELECT COUNT(*) FROM commandes_achat_lignes WHERE commande_id=? AND quantite_recue<quantite',(order_id,)).fetchone()[0]
                self.db.execute('UPDATE commandes_achat SET statut=? WHERE id=?',('RECUE' if not left else 'PARTIELLE',order_id))
            self.audit('RECEPTION COMMANDE ACHAT','commandes_achat',order_id,f'{qty} unité(s) reçue(s)')
        self.form_popup('Réception partielle / totale',[('ligne','Produit commandé','spinner',opts),('quantite','Quantité reçue maintenant','int','1'),('paye','Montant payé maintenant FCFA','text','0'),('mode','Mode de paiement','spinner',list(MODES))],save)

    def audit(self, action, table=None, row_id=None, details=''):
        with self.db:
            self.db.execute('INSERT INTO journal_actions(date,utilisateur,action,table_cible,ligne_id,details) VALUES(?,?,?,?,?,?)',
                (datetime.now().isoformat(timespec='seconds'),'Administrateur',action,table,row_id,str(details)[:500]))

    def start_inventory(self):
        if self.db.execute("SELECT 1 FROM inventaires WHERE statut='OUVERT'").fetchone():
            return self.popup_msg('Un inventaire est déjà ouvert.')
        products=self.db.execute('SELECT id,stock FROM produits ORDER BY id').fetchall()
        if not products: return self.popup_msg('Le catalogue est vide.')
        with self.db:
            cur=self.db.execute("INSERT INTO inventaires(code,date_ouverture,statut) VALUES(?,?,?)",
                ('INV-'+datetime.now().strftime('%Y%m%d-%H%M%S'),today(),'OUVERT'))
            iid=cur.lastrowid
            self.db.executemany('INSERT INTO inventaire_lignes(inventaire_id,produit_id,stock_theorique) VALUES(?,?,?)',[(iid,pid,qty) for pid,qty in products])
            self.db.execute('INSERT INTO sessions_inventaire(inventaire_id,date,action,details) VALUES(?,?,?,?)',(iid,today(),'OUVERTURE',f'{len(products)} produits'))
        self.audit('OUVERTURE INVENTAIRE','inventaires',iid)
        self.popup_msg(f'Inventaire {iid} ouvert. Saisis les quantités physiques.')
        self.refresh()

    def inventory_count_popup(self,iid):
        rows=self.db.execute('SELECT l.produit_id,p.nom,l.stock_theorique FROM inventaire_lignes l JOIN produits p ON p.id=l.produit_id WHERE l.inventaire_id=? ORDER BY p.nom LIMIT 500',(iid,)).fetchall()
        if not rows: return self.popup_msg('Aucune ligne à compter.')
        opts=[f'{pid}|{name} (théorique {qty})' for pid,name,qty in rows]
        def save(v):
            pid=int(v['produit'].split('|')[0]); physical=int(v['physique'])
            if physical<0: raise ValueError('Quantité négative interdite.')
            theory=next(r[2] for r in rows if r[0]==pid)
            with self.db:
                self.db.execute('UPDATE inventaire_lignes SET stock_physique=?,ecart=? WHERE inventaire_id=? AND produit_id=?',(physical,physical-theory,iid,pid))
                self.db.execute('INSERT INTO sessions_inventaire(inventaire_id,date,action,details) VALUES(?,?,?,?)',(iid,today(),'COMPTAGE',f'Produit {pid} : {physical}'))
            self.audit('COMPTAGE INVENTAIRE','inventaire_lignes',pid,f'Inventaire {iid}')
        self.form_popup('Comptage physique',[('produit','Produit','spinner',opts),('physique','Quantité réellement comptée','int','0')],save)

    def close_inventory(self,iid):
        missing=self.db.execute('SELECT COUNT(*) FROM inventaire_lignes WHERE inventaire_id=? AND stock_physique IS NULL',(iid,)).fetchone()[0]
        if missing: return self.popup_msg(f'Inventaire incomplet : {missing} produit(s) non compté(s).')
        lines=self.db.execute('SELECT produit_id,stock_theorique,stock_physique,ecart FROM inventaire_lignes WHERE inventaire_id=? AND COALESCE(ecart,0)<>0',(iid,)).fetchall()
        with self.db:
            for pid,theory,physical,diff in lines:
                self.db.execute('UPDATE produits SET stock=? WHERE id=?',(physical,pid))
                self.db.execute('INSERT INTO mouvements_stock(date,produit_id,type,quantite,motif) VALUES(?,?,?,?,?)',(today(),pid,'AJUSTEMENT',abs(diff),f'Inventaire INV-{iid:06d} : {theory} vers {physical}'))
            self.db.execute("UPDATE inventaires SET statut='CLOTURE',date_cloture=? WHERE id=?",(today(),iid))
            self.db.execute('INSERT INTO sessions_inventaire(inventaire_id,date,action,details) VALUES(?,?,?,?)',(iid,today(),'CLOTURE',f'{len(lines)} écarts'))
        self.audit('CLOTURE INVENTAIRE','inventaires',iid,f'{len(lines)} écarts')
        self.popup_msg(f'Inventaire clôturé : {len(lines)} écart(s) appliqué(s).')
        self.refresh()

    def return_popup(self):
        invoices=self.db.execute('SELECT id FROM factures ORDER BY id DESC LIMIT 300').fetchall()
        products=self.db.execute('SELECT id,nom,stock FROM produits ORDER BY nom LIMIT 1000').fetchall()
        if not products: return self.popup_msg('Aucun produit au catalogue.')
        def save(v):
            pid=int(v['produit'].split('|')[0]); qty=int(v['quantite'])
            if qty<=0: raise ValueError('Quantité invalide.')
            p=self.db.execute('SELECT prix_vente FROM produits WHERE id=?',(pid,)).fetchone()
            if not p: raise ValueError('Produit introuvable.')
            inv=int(v['facture'].split('|')[0]) if v['facture']!='Sans facture' else None
            action=v['action']; amount=qty*(p[0] or 0)
            code='RET-'+datetime.now().strftime('%Y%m%d%H%M%S%f')
            with self.db:
                cur=self.db.execute('INSERT INTO retours(code,date,facture_id,produit_id,quantite,montant,motif,action) VALUES(?,?,?,?,?,?,?,?)',(code,today(),inv,pid,qty,amount,v['motif'] or 'Non précisé',action))
                if action=='REINTEGRER':
                    self.db.execute('UPDATE produits SET stock=stock+? WHERE id=?',(qty,pid))
                    self.db.execute('INSERT INTO mouvements_stock(date,produit_id,type,quantite,motif) VALUES(?,?,?,?,?)',(today(),pid,'RETOUR',qty,code))
            self.audit('RETOUR CLIENT','retours',cur.lastrowid,code)
        self.form_popup('Retour client',[('facture','Facture','spinner',['Sans facture']+[f'{i}|F-{i:05d}' for (i,) in invoices]),('produit','Produit','spinner',[f'{i}|{n} (stock {s})' for i,n,s in products]),('quantite','Quantité retournée','int','1'),('action','Traitement stock','spinner',['REINTEGRER','NON_REINTEGRER']),('motif','Motif du retour','text','')],save)

    def expense_popup(self):
        def save(v):
            amount=num(v['montant'])
            if amount<=0 or not v['libelle']: raise ValueError('Libellé et montant positif obligatoires.')
            with self.db:
                cur=self.db.execute('INSERT INTO depenses(date,categorie,libelle,montant,mode,reference) VALUES(?,?,?,?,?,?)',(today(),v['categorie'],v['libelle'],amount,v['mode'],v['reference']))
                self.db.execute('INSERT INTO caisse(date,sens,libelle,montant) VALUES(?,?,?,?)',(today(),'sortie',f"Dépense {v['categorie']} : {v['libelle']}",amount))
            self.audit('DEPENSE','depenses',cur.lastrowid,v['libelle'])
        self.form_popup('Nouvelle dépense',[('categorie','Catégorie','spinner',['Loyer','Transport','Salaire','Électricité','Téléphone','Entretien','Autre']),('libelle','Description','text',''),('montant','Montant FCFA','text',''),('mode','Mode','spinner',list(MODES)),('reference','Référence / justificatif','text','')],save)

    def check_integrity(self):
        integrity=self.db.execute('PRAGMA integrity_check').fetchone()[0]
        fk=self.db.execute('PRAGMA foreign_key_check').fetchall()
        self.popup_msg(f'Intégrité SQLite : {integrity}\\nAnomalies de clés étrangères : {len(fk)}','Diagnostic base')

    def export_audit_csv(self):
        rows=self.db.execute('SELECT date,utilisateur,action,table_cible,ligne_id,details,evenement,avant,apres,origine FROM journal_actions ORDER BY id')
        self._export_rows('journal_actions.csv',['Date','Utilisateur','Action','Table','ID ligne','Détails','Événement','Avant (JSON)','Après (JSON)','Origine'],rows)

    def cash_closure_popup(self):
        theoretical=self.db.execute("SELECT COALESCE(SUM(CASE WHEN sens='entree' THEN montant ELSE -montant END),0) FROM caisse WHERE date=?",(today(),)).fetchone()[0]
        def save(v):
            counted=num(v['compte'])
            with self.db:
                cur=self.db.execute('INSERT INTO clotures_caisse(date,solde_theorique,solde_compte,ecart,observation) VALUES(?,?,?,?,?)',(today(),theoretical,counted,counted-theoretical,v['observation']))
            self.audit('CLOTURE CAISSE','clotures_caisse',cur.lastrowid)
            self.popup_msg(f'Théorique : {fmt(theoretical)} FCFA\\nCompté : {fmt(counted)} FCFA\\nÉcart : {fmt(counted-theoretical)} FCFA')
        self.form_popup('Clôture de caisse',[('compte','Montant réellement compté','text',fmt(theoretical)),('observation','Observation','text','')],save)

    def on_stop(self):
        try: self.db.close()
        except Exception: pass

if __name__=='__main__':
    ERPApp().run()
