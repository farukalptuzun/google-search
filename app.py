"""
Lead Scraper — Türkiye işletme iletişim bilgisi toplayıcı (Streamlit).
Kişisel kullanım için şehir/ilçe bazlı Google Places veya Apify araması yapar.
"""

from __future__ import annotations

import io
import os
import re
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Callable

import pandas as pd
import requests
import streamlit as st
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError, PyMongoError


# ---------------------------------------------------------------------------
# Türkiye İl / İlçe Veri Seti
# ---------------------------------------------------------------------------

# Türkiye il ve ilçe verileri (81 il, 973 ilçe)
# Kaynak: https://api.turkiyeapi.dev/v2/datasets/

TURKIYE_IL_ILCE: dict[str, list[str]] = {'Adana': ['Aladağ',
           'Ceyhan',
           'Feke',
           'Karaisalı',
           'Karataş',
           'Kozan',
           'Pozantı',
           'Saimbeyli',
           'Sarıçam',
           'Seyhan',
           'Tufanbeyli',
           'Yumurtalık',
           'Yüreğir',
           'Çukurova',
           'İmamoğlu'],
 'Adıyaman': ['Besni', 'Gerger', 'Gölbaşı', 'Kahta', 'Merkez', 'Samsat', 'Sincik', 'Tut', 'Çelikhan'],
 'Afyonkarahisar': ['Bayat',
                    'Başmakçı',
                    'Bolvadin',
                    'Dazkırı',
                    'Dinar',
                    'Emirdağ',
                    'Evciler',
                    'Hocalar',
                    'Kızılören',
                    'Merkez',
                    'Sandıklı',
                    'Sinanpaşa',
                    'Sultandağı',
                    'Çay',
                    'Çobanlar',
                    'İhsaniye',
                    'İscehisar',
                    'Şuhut'],
 'Aksaray': ['Ağaçören', 'Eskil', 'Gülağaç', 'Güzelyurt', 'Merkez', 'Ortaköy', 'Sarıyahşi', 'Sultanhanı'],
 'Amasya': ['Göynücek', 'Gümüşhacıköy', 'Hamamözü', 'Merkez', 'Merzifon', 'Suluova', 'Taşova'],
 'Ankara': ['Akyurt',
            'Altındağ',
            'Ayaş',
            'Bala',
            'Beypazarı',
            'Elmadağ',
            'Etimesgut',
            'Evren',
            'Gölbaşı',
            'Güdül',
            'Haymana',
            'Kahramankazan',
            'Kalecik',
            'Keçiören',
            'Kızılcahamam',
            'Mamak',
            'Nallıhan',
            'Polatlı',
            'Pursaklar',
            'Sincan',
            'Yenimahalle',
            'Çamlıdere',
            'Çankaya',
            'Çubuk',
            'Şereflikoçhisar'],
 'Antalya': ['Akseki',
             'Aksu',
             'Alanya',
             'Demre',
             'Döşemealtı',
             'Elmalı',
             'Finike',
             'Gazipaşa',
             'Gündoğmuş',
             'Kaş',
             'Kemer',
             'Kepez',
             'Konyaaltı',
             'Korkuteli',
             'Kumluca',
             'Manavgat',
             'Muratpaşa',
             'Serik',
             'İbradı'],
 'Ardahan': ['Damal', 'Göle', 'Hanak', 'Merkez', 'Posof', 'Çıldır'],
 'Artvin': ['Ardanuç', 'Arhavi', 'Borçka', 'Hopa', 'Kemalpaşa', 'Merkez', 'Murgul', 'Yusufeli', 'Şavşat'],
 'Aydın': ['Bozdoğan',
           'Buharkent',
           'Didim',
           'Efeler',
           'Germencik',
           'Karacasu',
           'Karpuzlu',
           'Koçarlı',
           'Kuyucak',
           'Kuşadası',
           'Köşk',
           'Nazilli',
           'Sultanhisar',
           'Söke',
           'Yenipazar',
           'Çine',
           'İncirliova'],
 'Ağrı': ['Diyadin', 'Doğubayazıt', 'Eleşkirt', 'Hamur', 'Merkez', 'Patnos', 'Taşlıçay', 'Tutak'],
 'Balıkesir': ['Altıeylül',
               'Ayvalık',
               'Balya',
               'Bandırma',
               'Bigadiç',
               'Burhaniye',
               'Dursunbey',
               'Edremit',
               'Erdek',
               'Gömeç',
               'Gönen',
               'Havran',
               'Karesi',
               'Kepsut',
               'Manyas',
               'Marmara',
               'Savaştepe',
               'Susurluk',
               'Sındırgı',
               'İvrindi'],
 'Bartın': ['Amasra', 'Kurucaşile', 'Merkez', 'Ulus'],
 'Batman': ['Beşiri', 'Gercüş', 'Hasankeyf', 'Kozluk', 'Merkez', 'Sason'],
 'Bayburt': ['Aydıntepe', 'Demirözü', 'Merkez'],
 'Bilecik': ['Bozüyük', 'Gölpazarı', 'Merkez', 'Osmaneli', 'Pazaryeri', 'Söğüt', 'Yenipazar', 'İnhisar'],
 'Bingöl': ['Adaklı', 'Genç', 'Karlıova', 'Kiğı', 'Merkez', 'Solhan', 'Yayladere', 'Yedisu'],
 'Bitlis': ['Adilcevaz', 'Ahlat', 'Güroymak', 'Hizan', 'Merkez', 'Mutki', 'Tatvan'],
 'Bolu': ['Dörtdivan', 'Gerede', 'Göynük', 'Kıbrıscık', 'Mengen', 'Merkez', 'Mudurnu', 'Seben', 'Yeniçağa'],
 'Burdur': ['Altınyayla',
            'Ağlasun',
            'Bucak',
            'Gölhisar',
            'Karamanlı',
            'Kemer',
            'Merkez',
            'Tefenni',
            'Yeşilova',
            'Çavdır',
            'Çeltikçi'],
 'Bursa': ['Büyükorhan',
           'Gemlik',
           'Gürsu',
           'Harmancık',
           'Karacabey',
           'Keles',
           'Kestel',
           'Mudanya',
           'Mustafakemalpaşa',
           'Nilüfer',
           'Orhaneli',
           'Orhangazi',
           'Osmangazi',
           'Yenişehir',
           'Yıldırım',
           'İnegöl',
           'İznik'],
 'Denizli': ['Acıpayam',
             'Babadağ',
             'Baklan',
             'Bekilli',
             'Beyağaç',
             'Bozkurt',
             'Buldan',
             'Güney',
             'Honaz',
             'Kale',
             'Merkezefendi',
             'Pamukkale',
             'Sarayköy',
             'Serinhisar',
             'Tavas',
             'Çal',
             'Çameli',
             'Çardak',
             'Çivril'],
 'Diyarbakır': ['Bağlar',
                'Bismil',
                'Dicle',
                'Ergani',
                'Eğil',
                'Hani',
                'Hazro',
                'Kayapınar',
                'Kocaköy',
                'Kulp',
                'Lice',
                'Silvan',
                'Sur',
                'Yenişehir',
                'Çermik',
                'Çüngüş',
                'Çınar'],
 'Düzce': ['Akçakoca', 'Cumayeri', 'Gölyaka', 'Gümüşova', 'Kaynaşlı', 'Merkez', 'Yığılca', 'Çilimli'],
 'Edirne': ['Enez', 'Havsa', 'Keşan', 'Lalapaşa', 'Meriç', 'Merkez', 'Süloğlu', 'Uzunköprü', 'İpsala'],
 'Elazığ': ['Alacakaya',
            'Arıcak',
            'Ağın',
            'Baskil',
            'Karakoçan',
            'Keban',
            'Kovancılar',
            'Maden',
            'Merkez',
            'Palu',
            'Sivrice'],
 'Erzincan': ['Kemah', 'Kemaliye', 'Merkez', 'Otlukbeli', 'Refahiye', 'Tercan', 'Çayırlı', 'Üzümlü', 'İliç'],
 'Erzurum': ['Aziziye',
             'Aşkale',
             'Horasan',
             'Hınıs',
             'Karayazı',
             'Karaçoban',
             'Köprüköy',
             'Narman',
             'Oltu',
             'Olur',
             'Palandöken',
             'Pasinler',
             'Pazaryolu',
             'Tekman',
             'Tortum',
             'Uzundere',
             'Yakutiye',
             'Çat',
             'İspir',
             'Şenkaya'],
 'Eskişehir': ['Alpu',
               'Beylikova',
               'Günyüzü',
               'Han',
               'Mahmudiye',
               'Mihalgazi',
               'Mihalıççık',
               'Odunpazarı',
               'Sarıcakaya',
               'Seyitgazi',
               'Sivrihisar',
               'Tepebaşı',
               'Çifteler',
               'İnönü'],
 'Gaziantep': ['Araban', 'Karkamış', 'Nizip', 'Nurdağı', 'Oğuzeli', 'Yavuzeli', 'İslahiye', 'Şahinbey', 'Şehitkamil'],
 'Giresun': ['Alucra',
             'Bulancak',
             'Dereli',
             'Doğankent',
             'Espiye',
             'Eynesil',
             'Görele',
             'Güce',
             'Keşap',
             'Merkez',
             'Piraziz',
             'Tirebolu',
             'Yağlıdere',
             'Çamoluk',
             'Çanakçı',
             'Şebinkarahisar'],
 'Gümüşhane': ['Kelkit', 'Köse', 'Kürtün', 'Merkez', 'Torul', 'Şiran'],
 'Hakkari': ['Derecik', 'Merkez', 'Yüksekova', 'Çukurca', 'Şemdinli'],
 'Hatay': ['Altınözü',
           'Antakya',
           'Arsuz',
           'Belen',
           'Defne',
           'Dörtyol',
           'Erzin',
           'Hassa',
           'Kumlu',
           'Kırıkhan',
           'Payas',
           'Reyhanlı',
           'Samandağ',
           'Yayladağı',
           'İskenderun'],
 'Isparta': ['Aksu',
             'Atabey',
             'Eğirdir',
             'Gelendost',
             'Gönen',
             'Keçiborlu',
             'Merkez',
             'Senirkent',
             'Sütçüler',
             'Uluborlu',
             'Yalvaç',
             'Yenişarbademli',
             'Şarkikaraağaç'],
 'Iğdır': ['Aralık', 'Karakoyunlu', 'Merkez', 'Tuzluca'],
 'Kahramanmaraş': ['Afşin',
                   'Andırın',
                   'Dulkadiroğlu',
                   'Ekinözü',
                   'Elbistan',
                   'Göksun',
                   'Nurhak',
                   'Onikişubat',
                   'Pazarcık',
                   'Türkoğlu',
                   'Çağlayancerit'],
 'Karabük': ['Eflani', 'Eskipazar', 'Merkez', 'Ovacık', 'Safranbolu', 'Yenice'],
 'Karaman': ['Ayrancı', 'Başyayla', 'Ermenek', 'Kazımkarabekir', 'Merkez', 'Sarıveliler'],
 'Kars': ['Akyaka', 'Arpaçay', 'Digor', 'Kağızman', 'Merkez', 'Sarıkamış', 'Selim', 'Susuz'],
 'Kastamonu': ['Abana',
               'Araç',
               'Azdavay',
               'Ağlı',
               'Bozkurt',
               'Cide',
               'Daday',
               'Devrekani',
               'Doğanyurt',
               'Hanönü',
               'Küre',
               'Merkez',
               'Pınarbaşı',
               'Seydiler',
               'Taşköprü',
               'Tosya',
               'Çatalzeytin',
               'İhsangazi',
               'İnebolu',
               'Şenpazar'],
 'Kayseri': ['Akkışla',
             'Bünyan',
             'Develi',
             'Felahiye',
             'Hacılar',
             'Kocasinan',
             'Melikgazi',
             'Pınarbaşı',
             'Sarıoğlan',
             'Sarız',
             'Talas',
             'Tomarza',
             'Yahyalı',
             'Yeşilhisar',
             'Özvatan',
             'İncesu'],
 'Kilis': ['Elbeyli', 'Merkez', 'Musabeyli', 'Polateli'],
 'Kocaeli': ['Başiskele',
             'Darıca',
             'Derince',
             'Dilovası',
             'Gebze',
             'Gölcük',
             'Kandıra',
             'Karamürsel',
             'Kartepe',
             'Körfez',
             'Çayırova',
             'İzmit'],
 'Konya': ['Ahırlı',
           'Akören',
           'Akşehir',
           'Altınekin',
           'Beyşehir',
           'Bozkır',
           'Cihanbeyli',
           'Derbent',
           'Derebucak',
           'Doğanhisar',
           'Emirgazi',
           'Ereğli',
           'Güneysınır',
           'Hadim',
           'Halkapınar',
           'Hüyük',
           'Ilgın',
           'Kadınhanı',
           'Karapınar',
           'Karatay',
           'Kulu',
           'Meram',
           'Sarayönü',
           'Selçuklu',
           'Seydişehir',
           'Taşkent',
           'Tuzlukçu',
           'Yalıhüyük',
           'Yunak',
           'Çeltik',
           'Çumra'],
 'Kütahya': ['Altıntaş',
             'Aslanapa',
             'Domaniç',
             'Dumlupınar',
             'Emet',
             'Gediz',
             'Hisarcık',
             'Merkez',
             'Pazarlar',
             'Simav',
             'Tavşanlı',
             'Çavdarhisar',
             'Şaphane'],
 'Kırklareli': ['Babaeski', 'Demirköy', 'Kofçaz', 'Lüleburgaz', 'Merkez', 'Pehlivanköy', 'Pınarhisar', 'Vize'],
 'Kırıkkale': ['Bahşılı', 'Balışeyh', 'Delice', 'Karakeçili', 'Keskin', 'Merkez', 'Sulakyurt', 'Yahşihan', 'Çelebi'],
 'Kırşehir': ['Akpınar', 'Akçakent', 'Boztepe', 'Kaman', 'Merkez', 'Mucur', 'Çiçekdağı'],
 'Malatya': ['Akçadağ',
             'Arapgir',
             'Arguvan',
             'Battalgazi',
             'Darende',
             'Doğanyol',
             'Doğanşehir',
             'Hekimhan',
             'Kale',
             'Kuluncak',
             'Pütürge',
             'Yazıhan',
             'Yeşilyurt'],
 'Manisa': ['Ahmetli',
            'Akhisar',
            'Alaşehir',
            'Demirci',
            'Gölmarmara',
            'Gördes',
            'Kula',
            'Köprübaşı',
            'Kırkağaç',
            'Salihli',
            'Saruhanlı',
            'Sarıgöl',
            'Selendi',
            'Soma',
            'Turgutlu',
            'Yunusemre',
            'Şehzadeler'],
 'Mardin': ['Artuklu',
            'Dargeçit',
            'Derik',
            'Kızıltepe',
            'Mazıdağı',
            'Midyat',
            'Nusaybin',
            'Savur',
            'Yeşilli',
            'Ömerli'],
 'Mersin': ['Akdeniz',
            'Anamur',
            'Aydıncık',
            'Bozyazı',
            'Erdemli',
            'Gülnar',
            'Mezitli',
            'Mut',
            'Silifke',
            'Tarsus',
            'Toroslar',
            'Yenişehir',
            'Çamlıyayla'],
 'Muğla': ['Bodrum',
           'Dalaman',
           'Datça',
           'Fethiye',
           'Kavaklıdere',
           'Köyceğiz',
           'Marmaris',
           'Menteşe',
           'Milas',
           'Ortaca',
           'Seydikemer',
           'Ula',
           'Yatağan'],
 'Muş': ['Bulanık', 'Hasköy', 'Korkut', 'Malazgirt', 'Merkez', 'Varto'],
 'Nevşehir': ['Acıgöl', 'Avanos', 'Derinkuyu', 'Gülşehir', 'Hacıbektaş', 'Kozaklı', 'Merkez', 'Ürgüp'],
 'Niğde': ['Altunhisar', 'Bor', 'Merkez', 'Ulukışla', 'Çamardı', 'Çiftlik'],
 'Ordu': ['Akkuş',
          'Altınordu',
          'Aybastı',
          'Fatsa',
          'Gölköy',
          'Gülyalı',
          'Gürgentepe',
          'Kabadüz',
          'Kabataş',
          'Korgan',
          'Kumru',
          'Mesudiye',
          'Perşembe',
          'Ulubey',
          'Çamaş',
          'Çatalpınar',
          'Çaybaşı',
          'Ünye',
          'İkizce'],
 'Osmaniye': ['Bahçe', 'Düziçi', 'Hasanbeyli', 'Kadirli', 'Merkez', 'Sumbas', 'Toprakkale'],
 'Rize': ['Ardeşen',
          'Derepazarı',
          'Fındıklı',
          'Güneysu',
          'Hemşin',
          'Kalkandere',
          'Merkez',
          'Pazar',
          'Çamlıhemşin',
          'Çayeli',
          'İkizdere',
          'İyidere'],
 'Sakarya': ['Adapazarı',
             'Akyazı',
             'Arifiye',
             'Erenler',
             'Ferizli',
             'Geyve',
             'Hendek',
             'Karapürçek',
             'Karasu',
             'Kaynarca',
             'Kocaali',
             'Pamukova',
             'Sapanca',
             'Serdivan',
             'Söğütlü',
             'Taraklı'],
 'Samsun': ['19 Mayıs',
            'Alaçam',
            'Asarcık',
            'Atakum',
            'Ayvacık',
            'Bafra',
            'Canik',
            'Havza',
            'Kavak',
            'Ladik',
            'Salıpazarı',
            'Tekkeköy',
            'Terme',
            'Vezirköprü',
            'Yakakent',
            'Çarşamba',
            'İlkadım'],
 'Siirt': ['Baykan', 'Eruh', 'Kurtalan', 'Merkez', 'Pervari', 'Tillo', 'Şirvan'],
 'Sinop': ['Ayancık', 'Boyabat', 'Dikmen', 'Durağan', 'Erfelek', 'Gerze', 'Merkez', 'Saraydüzü', 'Türkeli'],
 'Sivas': ['Akıncılar',
           'Altınyayla',
           'Divriği',
           'Doğanşar',
           'Gemerek',
           'Gölova',
           'Gürün',
           'Hafik',
           'Kangal',
           'Koyulhisar',
           'Merkez',
           'Suşehri',
           'Ulaş',
           'Yıldızeli',
           'Zara',
           'İmranlı',
           'Şarkışla'],
 'Tekirdağ': ['Ergene',
              'Hayrabolu',
              'Kapaklı',
              'Malkara',
              'Marmaraereğlisi',
              'Muratlı',
              'Saray',
              'Süleymanpaşa',
              'Çerkezköy',
              'Çorlu',
              'Şarköy'],
 'Tokat': ['Almus',
           'Artova',
           'Başçiftlik',
           'Erbaa',
           'Merkez',
           'Niksar',
           'Pazar',
           'Reşadiye',
           'Sulusaray',
           'Turhal',
           'Yeşilyurt',
           'Zile'],
 'Trabzon': ['Akçaabat',
             'Araklı',
             'Arsin',
             'Beşikdüzü',
             'Dernekpazarı',
             'Düzköy',
             'Hayrat',
             'Köprübaşı',
             'Maçka',
             'Of',
             'Ortahisar',
             'Sürmene',
             'Tonya',
             'Vakfıkebir',
             'Yomra',
             'Çarşıbaşı',
             'Çaykara',
             'Şalpazarı'],
 'Tunceli': ['Hozat', 'Mazgirt', 'Merkez', 'Nazımiye', 'Ovacık', 'Pertek', 'Pülümür', 'Çemişgezek'],
 'Uşak': ['Banaz', 'Eşme', 'Karahallı', 'Merkez', 'Sivaslı', 'Ulubey'],
 'Van': ['Bahçesaray',
         'Başkale',
         'Edremit',
         'Erciş',
         'Gevaş',
         'Gürpınar',
         'Muradiye',
         'Saray',
         'Tuşba',
         'Çaldıran',
         'Çatak',
         'Özalp',
         'İpekyolu'],
 'Yalova': ['Altınova', 'Armutlu', 'Merkez', 'Termal', 'Çiftlikköy', 'Çınarcık'],
 'Yozgat': ['Akdağmadeni',
            'Aydıncık',
            'Boğazlıyan',
            'Kadışehri',
            'Merkez',
            'Saraykent',
            'Sarıkaya',
            'Sorgun',
            'Yenifakılı',
            'Yerköy',
            'Çandır',
            'Çayıralan',
            'Çekerek',
            'Şefaatli'],
 'Zonguldak': ['Alaplı', 'Devrek', 'Ereğli', 'Gökçebey', 'Kilimli', 'Kozlu', 'Merkez', 'Çaycuma'],
 'Çanakkale': ['Ayvacık',
               'Bayramiç',
               'Biga',
               'Bozcaada',
               'Eceabat',
               'Ezine',
               'Gelibolu',
               'Gökçeada',
               'Lapseki',
               'Merkez',
               'Yenice',
               'Çan'],
 'Çankırı': ['Atkaracalar',
             'Bayramören',
             'Eldivan',
             'Ilgaz',
             'Korgun',
             'Kurşunlu',
             'Kızılırmak',
             'Merkez',
             'Orta',
             'Yapraklı',
             'Çerkeş',
             'Şabanözü'],
 'Çorum': ['Alaca',
           'Bayat',
           'Boğazkale',
           'Dodurga',
           'Kargı',
           'Laçin',
           'Mecitözü',
           'Merkez',
           'Ortaköy',
           'Osmancık',
           'Oğuzlar',
           'Sungurlu',
           'Uğurludağ',
           'İskilip'],
 'İstanbul': ['Adalar',
              'Arnavutköy',
              'Ataşehir',
              'Avcılar',
              'Bahçelievler',
              'Bakırköy',
              'Bayrampaşa',
              'Bağcılar',
              'Başakşehir',
              'Beykoz',
              'Beylikdüzü',
              'Beyoğlu',
              'Beşiktaş',
              'Büyükçekmece',
              'Esenler',
              'Esenyurt',
              'Eyüpsultan',
              'Fatih',
              'Gaziosmanpaşa',
              'Güngören',
              'Kadıköy',
              'Kartal',
              'Kağıthane',
              'Küçükçekmece',
              'Maltepe',
              'Pendik',
              'Sancaktepe',
              'Sarıyer',
              'Silivri',
              'Sultanbeyli',
              'Sultangazi',
              'Tuzla',
              'Zeytinburnu',
              'Çatalca',
              'Çekmeköy',
              'Ümraniye',
              'Üsküdar',
              'Şile',
              'Şişli'],
 'İzmir': ['Aliağa',
           'Balçova',
           'Bayraklı',
           'Bayındır',
           'Bergama',
           'Beydağ',
           'Bornova',
           'Buca',
           'Dikili',
           'Foça',
           'Gaziemir',
           'Güzelbahçe',
           'Karabağlar',
           'Karaburun',
           'Karşıyaka',
           'Kemalpaşa',
           'Kiraz',
           'Konak',
           'Kınık',
           'Menderes',
           'Menemen',
           'Narlıdere',
           'Seferihisar',
           'Selçuk',
           'Tire',
           'Torbalı',
           'Urla',
           'Çeşme',
           'Çiğli',
           'Ödemiş'],
 'Şanlıurfa': ['Akçakale',
               'Birecik',
               'Bozova',
               'Ceylanpınar',
               'Eyyübiye',
               'Halfeti',
               'Haliliye',
               'Harran',
               'Hilvan',
               'Karaköprü',
               'Siverek',
               'Suruç',
               'Viranşehir'],
 'Şırnak': ['Beytüşşebap', 'Cizre', 'Güçlükonak', 'Merkez', 'Silopi', 'Uludere', 'İdil']}

# ---------------------------------------------------------------------------
# Sabitler
# ---------------------------------------------------------------------------

LEGACY_TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
LEGACY_PLACE_DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"
DEFAULT_GOOGLE_REFERER = "http://localhost:8501"
APIFY_ACTOR_ID = "compass/crawler-google-places"
MAX_SEARCH_PAGES = 2
REQUEST_DELAY_SEC = 0.35
PAGE_TOKEN_DELAY_SEC = 2.0
DETAILS_FIELDS = "name,formatted_phone_number"

COLUMN_FIRMA = "Firma Adı"
COLUMN_TELEFON = "Telefon Numarası"
DEFAULT_MONGO_URI = "mongodb://localhost:27017"
DEFAULT_MONGO_DB = "lead_scraper"
MONGO_PHONE_FIELD = "telefon_normalize"


# ---------------------------------------------------------------------------
# Yardımcı fonksiyonlar
# ---------------------------------------------------------------------------


def normalize_phone(phone: str) -> str:
    """Telefon numarasını karşılaştırma için yalnızca rakamlara indirger."""
    return re.sub(r"\D", "", phone or "")


def normalize_name(name: str) -> str:
    """Firma adını mükerrer kontrolü için normalize eder."""
    return re.sub(r"\s+", " ", (name or "").strip().lower())


def deduplicate_leads(leads: list[dict[str, str]]) -> list[dict[str, str]]:
    """
    Aynı telefon veya firma adına sahip kayıtları temizler.
    Birincil anahtar: normalize telefon; ikincil: normalize firma adı.
    """
    seen_phones: set[str] = set()
    seen_names: set[str] = set()
    unique: list[dict[str, str]] = []

    for lead in leads:
        phone_key = normalize_phone(lead.get(COLUMN_TELEFON, ""))
        name_key = normalize_name(lead.get(COLUMN_FIRMA, ""))

        if not phone_key:
            continue
        if phone_key in seen_phones:
            continue
        if name_key and name_key in seen_names:
            continue

        seen_phones.add(phone_key)
        if name_key:
            seen_names.add(name_key)
        unique.append(lead)

    return unique


def leads_to_txt(leads: list[dict[str, str]]) -> str:
    """TXT export formatı: Firma Adı - Telefon Numarası (satır satır)."""
    lines = [f"{lead[COLUMN_FIRMA]} - {lead[COLUMN_TELEFON]}" for lead in leads]
    return "\n".join(lines)


def get_mongo_settings(sidebar_uri: str, sidebar_db: str) -> tuple[str, str]:
    """MongoDB bağlantı ayarlarını sidebar, secrets veya ortam değişkeninden okur."""
    uri = sidebar_uri.strip()
    db_name = sidebar_db.strip()

    if not uri:
        for source in (
            lambda: st.secrets.get("MONGO_URI", ""),
            lambda: os.environ.get("MONGO_URI", ""),
        ):
            try:
                value = source()
                if value:
                    uri = value
                    break
            except (KeyError, FileNotFoundError, AttributeError):
                pass

    if not db_name:
        for source in (
            lambda: st.secrets.get("MONGO_DB", ""),
            lambda: os.environ.get("MONGO_DB", ""),
        ):
            try:
                value = source()
                if value:
                    db_name = value
                    break
            except (KeyError, FileNotFoundError, AttributeError):
                pass

    return uri or DEFAULT_MONGO_URI, db_name or DEFAULT_MONGO_DB


@contextmanager
def mongo_city_collection(sehir: str, mongo_uri: str, db_name: str):
    """Şehir adıyla adlandırılmış MongoDB koleksiyonuna bağlanır."""
    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=4000)
    try:
        client.admin.command("ping")
        collection = client[db_name][sehir]
        collection.create_index(MONGO_PHONE_FIELD, unique=True)
        yield collection
    finally:
        client.close()


def lead_doc_from_row(lead: dict[str, str], anahtar_kelime: str) -> dict | None:
    """DataFrame satırını MongoDB belgesine dönüştürür."""
    phone_norm = normalize_phone(lead.get(COLUMN_TELEFON, ""))
    firma = (lead.get(COLUMN_FIRMA) or "").strip()
    telefon = (lead.get(COLUMN_TELEFON) or "").strip()

    if not phone_norm or not firma:
        return None

    return {
        COLUMN_FIRMA: firma,
        COLUMN_TELEFON: telefon,
        MONGO_PHONE_FIELD: phone_norm,
        "anahtar_kelime": anahtar_kelime,
        "kaynak": "lead_scraper",
        "olusturulma": datetime.now(timezone.utc),
    }


def save_leads_to_mongo(
    sehir: str,
    leads: list[dict[str, str]],
    anahtar_kelime: str,
    mongo_uri: str,
    db_name: str,
) -> dict[str, int | str]:
    """
    Tarama sonuçlarını şehir koleksiyonuna kaydeder.
    Aynı telefon numarası varsa tekrar yazılmaz.
    """
    stats = {"eklenen": 0, "atlanan": 0, "gecersiz": 0}

    try:
        with mongo_city_collection(sehir, mongo_uri, db_name) as collection:
            for lead in leads:
                doc = lead_doc_from_row(lead, anahtar_kelime)
                if not doc:
                    stats["gecersiz"] += 1
                    continue

                try:
                    result = collection.update_one(
                        {MONGO_PHONE_FIELD: doc[MONGO_PHONE_FIELD]},
                        {"$setOnInsert": doc},
                        upsert=True,
                    )
                    if result.upserted_id:
                        stats["eklenen"] += 1
                    else:
                        stats["atlanan"] += 1
                except DuplicateKeyError:
                    stats["atlanan"] += 1

        stats["durum"] = "ok"
        return stats

    except PyMongoError as exc:
        return {
            "durum": "hata",
            "mesaj": str(exc),
            "eklenen": 0,
            "atlanan": 0,
            "gecersiz": 0,
        }


def load_leads_from_mongo(sehir: str, mongo_uri: str, db_name: str) -> pd.DataFrame:
    """Şehir koleksiyonundaki tüm lead kayıtlarını DataFrame olarak yükler."""
    try:
        with mongo_city_collection(sehir, mongo_uri, db_name) as collection:
            docs = list(
                collection.find(
                    {},
                    {
                        "_id": 0,
                        COLUMN_FIRMA: 1,
                        COLUMN_TELEFON: 1,
                    },
                ).sort(COLUMN_FIRMA, 1)
            )

        if not docs:
            return pd.DataFrame(columns=[COLUMN_FIRMA, COLUMN_TELEFON])

        return pd.DataFrame(docs, columns=[COLUMN_FIRMA, COLUMN_TELEFON])

    except PyMongoError as exc:
        st.error(f"MongoDB okuma hatası: {exc}")
        return pd.DataFrame(columns=[COLUMN_FIRMA, COLUMN_TELEFON])


def count_city_leads(sehir: str, mongo_uri: str, db_name: str) -> int | None:
    """Şehir koleksiyonundaki kayıt sayısını döndürür."""
    try:
        with mongo_city_collection(sehir, mongo_uri, db_name) as collection:
            return collection.count_documents({})
    except PyMongoError:
        return None


def get_api_key(provider: str, sidebar_key: str) -> str:
    """Sidebar, secrets.toml veya ortam değişkeninden API anahtarını okur."""
    if sidebar_key.strip():
        return sidebar_key.strip()

    if provider == "Google Places API":
        for source in (
            lambda: st.secrets.get("GOOGLE_PLACES_API_KEY", ""),
            lambda: os.environ.get("GOOGLE_PLACES_API_KEY", ""),
        ):
            try:
                value = source()
                if value:
                    return value
            except (KeyError, FileNotFoundError, AttributeError):
                pass
    else:
        for source in (
            lambda: st.secrets.get("APIFY_API_TOKEN", ""),
            lambda: os.environ.get("APIFY_API_TOKEN", ""),
        ):
            try:
                value = source()
                if value:
                    return value
            except (KeyError, FileNotFoundError, AttributeError):
                pass

    return ""


def get_google_referer(sidebar_referer: str) -> str:
    """HTTP referrer kısıtlı anahtarlar için Referer başlığı değerini döndürür."""
    if sidebar_referer.strip():
        return sidebar_referer.strip()

    for source in (
        lambda: st.secrets.get("GOOGLE_REFERER", ""),
        lambda: os.environ.get("GOOGLE_REFERER", ""),
    ):
        try:
            value = source()
            if value:
                return value
        except (KeyError, FileNotFoundError, AttributeError):
            pass

    return DEFAULT_GOOGLE_REFERER


def google_request_headers(referer: str) -> dict[str, str]:
    """Referrer kısıtlı API anahtarları için istek başlıklarını oluşturur."""
    referer = referer.strip()
    return {"Referer": referer} if referer else {}


def extract_legacy_error(data: dict) -> str:
    """Legacy Places API yanıtından hata mesajı çıkarır."""
    status = data.get("status", "UNKNOWN")
    message = data.get("error_message", "")
    return f"{status}: {message}" if message else status


def show_google_error_once(status_code: int, detail: str, query: str, referer: str = "") -> None:
    """Aynı kök hatayı ilçe başına tekrar tekrar göstermek yerine bir kez uyarır."""
    error_key = f"{status_code}:{detail}"
    if st.session_state.get("google_api_error_key") == error_key:
        return

    st.session_state.google_api_error_key = error_key

    if status_code == 403 or "REQUEST_DENIED" in detail or "referer" in detail.lower():
        st.error(
            f"**Google API erişim hatası** — İstek reddedildi.\n\n"
            f"**Google mesajı:** {detail}\n\n"
            "**Çözüm (referrer kısıtlı anahtar):**\n"
            f"1. Sol menüdeki **HTTP Referer** alanına Google Console'da tanımlı adresi yazın "
            f"(şu an: `{referer or 'boş'}`).\n"
            "2. Console → Credentials → API anahtarı → *Website restrictions* listesinde bu adres olmalı "
            "(ör. `http://localhost:8501/*`).\n"
            "3. **Places API** (legacy) etkin ve faturalandırma açık olmalı.\n\n"
            "**Alternatif:** Anahtar kısıtlamasını *None* yapın veya IP kısıtı kullanın.\n\n"
            f"Örnek sorgu: `{query}`"
        )
    else:
        st.warning(f"Google API hatası ({status_code}): {detail}")


# ---------------------------------------------------------------------------
# API entegrasyonları
# ---------------------------------------------------------------------------


def fetch_place_details(
    place_id: str,
    fallback_name: str,
    api_key: str,
    headers: dict[str, str],
    place_cache: dict[str, dict[str, str] | None],
) -> dict[str, str] | None:
    """Tek bir place_id için telefon bilgisini Legacy Details API ile çeker."""
    if place_id in place_cache:
        return place_cache[place_id]

    params = {
        "place_id": place_id,
        "fields": DETAILS_FIELDS,
        "key": api_key,
        "language": "tr",
    }

    try:
        response = requests.get(
            LEGACY_PLACE_DETAILS_URL,
            params=params,
            headers=headers,
            timeout=30,
        )
        data = response.json()
        status = data.get("status")

        if status != "OK":
            if status == "REQUEST_DENIED":
                show_google_error_once(403, extract_legacy_error(data), place_id, headers.get("Referer", ""))
            place_cache[place_id] = None
            return None

        result = data.get("result", {})
        phone = result.get("formatted_phone_number", "")
        name = result.get("name") or fallback_name

        if name and phone:
            lead = {COLUMN_FIRMA: name.strip(), COLUMN_TELEFON: phone.strip()}
            place_cache[place_id] = lead
            return lead

        place_cache[place_id] = None
        return None

    except requests.RequestException as exc:
        st.warning(f"Place Details hatası ({place_id}): {exc}")
        place_cache[place_id] = None
        return None
    finally:
        time.sleep(REQUEST_DELAY_SEC)


def search_google_places(
    query: str,
    api_key: str,
    referer: str,
    place_cache: dict[str, dict[str, str] | None],
) -> list[dict[str, str]]:
    """
    Legacy Places API: Text Search + Place Details.
    Referer başlığı ile HTTP referrer kısıtlı anahtarlar desteklenir.
    place_cache aynı işletmenin tekrar sorgulanmasını önler.
    """
    headers = google_request_headers(referer)
    params: dict[str, str] = {
        "query": query,
        "key": api_key,
        "language": "tr",
        "region": "tr",
    }

    leads: list[dict[str, str]] = []
    pending: dict[str, str] = {}

    try:
        for page in range(MAX_SEARCH_PAGES):
            response = requests.get(
                LEGACY_TEXT_SEARCH_URL,
                params=params,
                headers=headers,
                timeout=30,
            )
            data = response.json()
            status = data.get("status")

            if status == "ZERO_RESULTS":
                break

            if status != "OK":
                code = 403 if status == "REQUEST_DENIED" else 400
                show_google_error_once(code, extract_legacy_error(data), query, referer)
                break

            for place in data.get("results", []):
                place_id = place.get("place_id")
                name = place.get("name", "")
                if not place_id:
                    continue

                if place_id in place_cache:
                    cached = place_cache[place_id]
                    if cached:
                        leads.append(cached)
                    continue

                if place_id not in pending:
                    pending[place_id] = name

            next_page = data.get("next_page_token")
            if not next_page or page >= MAX_SEARCH_PAGES - 1:
                break

            time.sleep(PAGE_TOKEN_DELAY_SEC)
            params = {"pagetoken": next_page, "key": api_key}

        for place_id, name in pending.items():
            if place_id in place_cache:
                cached = place_cache[place_id]
                if cached:
                    leads.append(cached)
                continue

            lead = fetch_place_details(place_id, name, api_key, headers, place_cache)
            if lead:
                leads.append(lead)

    except requests.RequestException as exc:
        st.warning(f"Google bağlantı hatası ('{query}'): {exc}")

    return leads


def search_apify(query: str, api_token: str, max_places: int = 20) -> list[dict[str, str]]:
    """
    Apify Google Maps Scraper (compass/crawler-google-places) ile arama yapar.
    apify-client yüklü değilse kullanıcıya bilgi verir.
    """
    try:
        from apify_client import ApifyClient
    except ImportError:
        st.error("Apify kullanmak için: pip install apify-client")
        return []

    results: list[dict[str, str]] = []

    try:
        client = ApifyClient(api_token)
        run_input = {
            "searchStringsArray": [query],
            "maxCrawledPlacesPerSearch": max_places,
            "language": "tr",
            "countryCode": "tr",
        }
        run = client.actor(APIFY_ACTOR_ID).call(run_input=run_input)

        for item in client.dataset(run["defaultDatasetId"]).iterate_items():
            name = item.get("title") or item.get("name") or ""
            phone = item.get("phone") or item.get("phoneUnformatted") or ""
            if name and phone:
                results.append({COLUMN_FIRMA: name.strip(), COLUMN_TELEFON: phone.strip()})

    except Exception as exc:
        st.warning(f"Apify hatası ('{query}'): {exc}")

    return results


def scrape_city(
    sehir: str,
    anahtar_kelime: str,
    ilceler: list[str],
    search_fn: Callable[[str], list[dict[str, str]]],
    progress_bar,
    status_text,
) -> pd.DataFrame:
    """Seçilen şehrin tüm ilçelerini dolaşarak lead listesi oluşturur."""
    all_leads: list[dict[str, str]] = []
    total = len(ilceler)

    for index, ilce in enumerate(ilceler):
        query = f"{sehir} {ilce} {anahtar_kelime}"
        pct = int(((index + 1) / total) * 100)
        status_text.markdown(
            f"""
            <div class="scan-status">
                <div class="scan-status-label">Aktif Tarama</div>
                <div class="scan-status-title">{ilce}</div>
                <div class="scan-status-meta">
                    {index + 1} / {total} ilçe &nbsp;·&nbsp; %{pct} tamamlandı
                </div>
                <div class="scan-query">"{query}"</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        progress_bar.progress((index + 1) / total, text=f"{ilce} taranıyor... ({index + 1}/{total})")

        try:
            district_leads = search_fn(query)
            all_leads.extend(district_leads)
        except Exception as exc:
            st.warning(f"{ilce} ilçesi atlandı: {exc}")

        time.sleep(REQUEST_DELAY_SEC)

    unique_leads = deduplicate_leads(all_leads)
    return pd.DataFrame(unique_leads, columns=[COLUMN_FIRMA, COLUMN_TELEFON])


# ---------------------------------------------------------------------------
# Streamlit arayüzü
# ---------------------------------------------------------------------------


def inject_custom_css() -> None:
    """Uygulamaya özel modern arayüz stillerini enjekte eder."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&display=swap');

        :root {
            --primary: #4f46e5;
            --primary-dark: #3730a3;
            --accent: #06b6d4;
            --success: #10b981;
            --surface: #ffffff;
            --surface-2: #f8fafc;
            --border: #e2e8f0;
            --text: #0f172a;
            --muted: #64748b;
            --shadow: 0 10px 30px rgba(15, 23, 42, 0.08);
        }

        html, body, [class*="css"] {
            font-family: 'DM Sans', sans-serif;
        }

        #MainMenu, footer, header { visibility: hidden; }

        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2rem;
            max-width: 1200px;
        }

        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0f172a 0%, #1e293b 100%);
            border-right: 1px solid rgba(255,255,255,0.06);
        }

        section[data-testid="stSidebar"] * {
            color: #e2e8f0 !important;
        }

        section[data-testid="stSidebar"] .stRadio label,
        section[data-testid="stSidebar"] label {
            color: #cbd5e1 !important;
        }

        section[data-testid="stSidebar"] input {
            background: rgba(255,255,255,0.08) !important;
            border: 1px solid rgba(255,255,255,0.12) !important;
            color: #f8fafc !important;
        }

        .hero {
            background: linear-gradient(135deg, #4f46e5 0%, #7c3aed 45%, #06b6d4 100%);
            border-radius: 20px;
            padding: 2rem 2.2rem;
            margin-bottom: 1.5rem;
            color: white;
            box-shadow: var(--shadow);
            position: relative;
            overflow: hidden;
        }

        .hero::after {
            content: "";
            position: absolute;
            top: -40%;
            right: -8%;
            width: 280px;
            height: 280px;
            background: rgba(255,255,255,0.12);
            border-radius: 50%;
        }

        .hero-badge {
            display: inline-block;
            background: rgba(255,255,255,0.18);
            border: 1px solid rgba(255,255,255,0.25);
            border-radius: 999px;
            padding: 0.3rem 0.85rem;
            font-size: 0.78rem;
            font-weight: 600;
            letter-spacing: 0.04em;
            text-transform: uppercase;
            margin-bottom: 0.75rem;
        }

        .hero h1 {
            margin: 0 0 0.5rem 0;
            font-size: 2.2rem;
            font-weight: 700;
            line-height: 1.15;
            color: white !important;
        }

        .hero p {
            margin: 0;
            font-size: 1.02rem;
            opacity: 0.92;
            max-width: 680px;
            color: rgba(255,255,255,0.95) !important;
        }

        .metric-card {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 16px;
            padding: 1.1rem 1.2rem;
            box-shadow: 0 4px 14px rgba(15, 23, 42, 0.04);
            height: 100%;
        }

        .metric-icon {
            font-size: 1.35rem;
            margin-bottom: 0.35rem;
        }

        .metric-value {
            font-size: 1.65rem;
            font-weight: 700;
            color: var(--text);
            line-height: 1.1;
        }

        .metric-label {
            font-size: 0.82rem;
            color: var(--muted);
            margin-top: 0.25rem;
            font-weight: 500;
        }

        .panel {
            background: var(--surface);
            border: 1px solid var(--border);
            border-radius: 18px;
            padding: 1.4rem 1.5rem;
            box-shadow: var(--shadow);
            margin-bottom: 1.25rem;
        }

        .panel-title {
            font-size: 1.05rem;
            font-weight: 700;
            color: var(--text);
            margin-bottom: 0.25rem;
        }

        .panel-subtitle {
            font-size: 0.88rem;
            color: var(--muted);
            margin-bottom: 1rem;
        }

        .query-preview {
            background: linear-gradient(90deg, #eef2ff, #ecfeff);
            border: 1px dashed #a5b4fc;
            border-radius: 12px;
            padding: 0.85rem 1rem;
            margin-top: 0.5rem;
            margin-bottom: 1rem;
            font-size: 0.92rem;
            color: #312e81;
        }

        .query-preview strong {
            color: #4338ca;
        }

        .scan-status {
            background: linear-gradient(90deg, #eff6ff, #f0fdf4);
            border: 1px solid #bfdbfe;
            border-left: 5px solid var(--primary);
            border-radius: 14px;
            padding: 1rem 1.15rem;
            margin: 0.75rem 0 1rem 0;
        }

        .scan-status-label {
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            color: var(--primary);
            font-weight: 700;
            margin-bottom: 0.2rem;
        }

        .scan-status-title {
            font-size: 1.25rem;
            font-weight: 700;
            color: var(--text);
        }

        .scan-status-meta {
            font-size: 0.88rem;
            color: var(--muted);
            margin-top: 0.15rem;
        }

        .scan-query {
            margin-top: 0.55rem;
            font-size: 0.84rem;
            color: #475569;
            font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
            background: rgba(255,255,255,0.75);
            border-radius: 8px;
            padding: 0.45rem 0.6rem;
        }

        .results-header {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            margin-bottom: 0.75rem;
        }

        .results-pill {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            background: #ecfdf5;
            color: #047857;
            border: 1px solid #a7f3d0;
            border-radius: 999px;
            padding: 0.35rem 0.8rem;
            font-size: 0.82rem;
            font-weight: 600;
        }

        .empty-state {
            text-align: center;
            padding: 2.5rem 1rem;
            color: var(--muted);
        }

        .empty-state-icon {
            font-size: 2.4rem;
            margin-bottom: 0.5rem;
        }

        .footer-note {
            text-align: center;
            color: var(--muted);
            font-size: 0.8rem;
            margin-top: 1.5rem;
            padding-top: 1rem;
            border-top: 1px solid var(--border);
        }

        div[data-testid="stProgress"] > div > div {
            background: linear-gradient(90deg, #4f46e5, #06b6d4);
            border-radius: 999px;
        }

        div[data-testid="stProgress"] > div {
            background-color: #e2e8f0;
            border-radius: 999px;
        }

        .stDownloadButton > button {
            border-radius: 12px !important;
            font-weight: 600 !important;
            border: 1px solid var(--border) !important;
            transition: all 0.2s ease !important;
        }

        .stDownloadButton > button:hover {
            border-color: var(--primary) !important;
            color: var(--primary) !important;
        }

        div[data-testid="stExpander"] {
            background: var(--surface-2);
            border: 1px solid var(--border);
            border-radius: 14px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
    """Üst hero bölümünü render eder."""
    st.markdown(
        """
        <div class="hero">
            <div class="hero-badge">Türkiye Lead Scraper</div>
            <h1>İşletme İletişim Bilgisi Toplayıcı</h1>
            <p>
                Seçtiğiniz şehrin tüm ilçelerinde anahtar kelimeye göre arama yapın,
                telefon numarası olan işletmeleri listeleyin ve dışa aktarın.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_metric_cards(
    secilen_sehir: str,
    ilce_sayisi: int,
    provider: str,
    mongo_count: int | None = None,
) -> None:
    """Özet metrik kartlarını gösterir."""
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-icon">📍</div>
                <div class="metric-value">{secilen_sehir}</div>
                <div class="metric-label">Seçili Şehir</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-icon">🗺️</div>
                <div class="metric-value">{ilce_sayisi}</div>
                <div class="metric-label">Taranacak İlçe</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c3:
        provider_short = "Google" if provider == "Google Places API" else "Apify"
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-icon">⚡</div>
                <div class="metric-value">{provider_short}</div>
                <div class="metric-label">Veri Kaynağı</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with c4:
        mongo_label = str(mongo_count) if mongo_count is not None else "—"
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-icon">🗄️</div>
                <div class="metric-value">{mongo_label}</div>
                <div class="metric-label">MongoDB ({secilen_sehir})</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def init_session_state() -> None:
    """Session state değişkenlerini başlatır."""
    if "results" not in st.session_state:
        st.session_state.results = pd.DataFrame(columns=[COLUMN_FIRMA, COLUMN_TELEFON])
    if "scanning" not in st.session_state:
        st.session_state.scanning = False
    if "last_sehir" not in st.session_state:
        st.session_state.last_sehir = ""
    if "google_api_error_key" not in st.session_state:
        st.session_state.google_api_error_key = None
    if "place_cache" not in st.session_state:
        st.session_state.place_cache = {}


def render_setup_expander() -> None:
    """Kurulum talimatlarını gösterir."""
    with st.expander("Kurulum ve API Anahtarı", expanded=False):
        tab1, tab2, tab3, tab4 = st.tabs(["Google API", "Apify", "MongoDB", "Çalıştırma"])
        with tab1:
            st.markdown(
                """
1. [Google Cloud Console](https://console.cloud.google.com/) üzerinden **Places API** etkinleştirin.
2. API anahtarınızı sol menüye girin.
3. Anahtarınız **HTTP referrer** ile kısıtlıysa, sol menüdeki Referer alanına
   Console'da tanımlı adresi yazın (ör. `http://localhost:8501`).

```toml
GOOGLE_PLACES_API_KEY = "AIza..."
GOOGLE_REFERER = "http://localhost:8501"
```
                """
            )
        with tab2:
            st.markdown(
                """
1. [Apify](https://apify.com/) hesabı oluşturun.
2. Token'ı sol menüye girin veya secrets dosyasına ekleyin:

```toml
APIFY_API_TOKEN = "apify_api_..."
```
                """
            )
        with tab3:
            st.markdown(
                """
1. Lokal MongoDB çalışıyor olmalı (`mongod` veya Docker).
2. Her şehir için koleksiyon adı **şehir ismi** olur (ör. `Ankara`, `Konya`).
3. Aynı telefon numarası tekrar yazılmaz; yalnızca yeni numaralar eklenir.

```bash
# Docker ile hızlı başlatma
docker run -d --name lead-mongo -p 27017:27017 mongo:7
```

```toml
MONGO_URI = "mongodb://localhost:27017"
MONGO_DB = "lead_scraper"
```
                """
            )
        with tab4:
            st.code("pip install -r requirements.txt\nstreamlit run app.py", language="bash")
            st.warning(
                "Legacy API: ilçe başına Text Search + işletme başına Place Details isteği atılır. "
                "place_id önbelleği tekrarlayan sorguları azaltır."
            )


def render_sidebar() -> tuple[str, str, str, str, str, bool]:
    """Sidebar API ve MongoDB ayarlarını render eder."""
    with st.sidebar:
        st.markdown("### Ayarlar")
        st.caption("Veri kaynağı ve API kimlik bilgileri")

        provider = st.radio(
            "Veri Kaynağı",
            options=["Google Places API", "Apify Google Maps"],
            index=0,
            help="Google Legacy Places API (Text Search + Details) kullanılır.",
        )

        st.divider()

        if provider == "Google Places API":
            st.markdown("**Google Places API**")
            st.caption("Text Search + Place Details (legacy, referrer uyumlu).")
            api_key_label = "API Anahtarı"
        else:
            st.markdown("**Apify Google Maps**")
            st.caption("compass/crawler-google-places actor'ü kullanılır.")
            api_key_label = "API Token"

        sidebar_api_key = st.text_input(
            api_key_label,
            type="password",
            key="api_key_input",
            placeholder="Anahtarınızı buraya yapıştırın",
        )

        google_referer = ""
        if provider == "Google Places API":
            google_referer = st.text_input(
                "HTTP Referer",
                value=DEFAULT_GOOGLE_REFERER,
                help=(
                    "API anahtarınız website referrer ile kısıtlıysa buraya Console'daki "
                    "adresi girin. Streamlit varsayılanı: http://localhost:8501"
                ),
                placeholder="http://localhost:8501",
            )

        if sidebar_api_key:
            st.success("API anahtarı girildi", icon="✅")
        else:
            st.info("Anahtar secrets.toml veya ortam değişkeninden de okunabilir.", icon="ℹ️")

        st.divider()
        st.markdown("### MongoDB")
        mongo_enabled = st.toggle("Tarama sonrası MongoDB'ye kaydet", value=True)
        mongo_uri = st.text_input("Mongo URI", value=DEFAULT_MONGO_URI, key="mongo_uri")
        mongo_db = st.text_input("Veritabanı", value=DEFAULT_MONGO_DB, key="mongo_db")
        st.caption("Koleksiyon adı = şehir ismi. Telefon numarası benzersiz anahtardır.")

        st.divider()
        st.markdown(
            "<small>81 il · 973 ilçe<br>MongoDB + place_id önbelleği</small>",
            unsafe_allow_html=True,
        )

    return provider, sidebar_api_key, google_referer, mongo_uri, mongo_db, mongo_enabled


def main() -> None:
    st.set_page_config(
        page_title="Lead Scraper | Türkiye",
        page_icon="📋",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    init_session_state()
    inject_custom_css()
    render_header()

    provider, sidebar_api_key, sidebar_referer, mongo_uri_input, mongo_db_input, mongo_enabled = render_sidebar()

    sehirler = sorted(TURKIYE_IL_ILCE.keys())
    mongo_uri, mongo_db = get_mongo_settings(mongo_uri_input, mongo_db_input)

    # Arama paneli
    st.markdown(
        """
        <div class="panel">
            <div class="panel-title">Arama Parametreleri</div>
            <div class="panel-subtitle">Şehir ve anahtar kelime seçerek taramayı başlatın</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns([1, 1.4], gap="large")
    with col1:
        secilen_sehir = st.selectbox(
            "Şehir Seçin",
            options=sehirler,
            index=sehirler.index("Konya") if "Konya" in sehirler else 0,
        )
    with col2:
        anahtar_kelime = st.text_input(
            "Anahtar Kelime",
            value="tabela reklam",
            placeholder="Örn: tabela reklam, diş kliniği, avukat...",
        )

    ilce_sayisi = len(TURKIYE_IL_ILCE[secilen_sehir])
    ornek_ilce = TURKIYE_IL_ILCE[secilen_sehir][0]
    ornek_sorgu = f"{secilen_sehir} {ornek_ilce} {anahtar_kelime or '...'}"
    mongo_count = count_city_leads(secilen_sehir, mongo_uri, mongo_db) if mongo_enabled else None

    st.markdown(
        f"""
        <div class="query-preview">
            <strong>Örnek sorgu formatı:</strong> "{ornek_sorgu}"
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_metric_cards(secilen_sehir, ilce_sayisi, provider, mongo_count)

    btn_col1, btn_col2, btn_col3 = st.columns([1.2, 1, 1.2])
    with btn_col1:
        start_scan = st.button(
            "Taramayı Başlat",
            type="primary",
            disabled=st.session_state.scanning,
            use_container_width=True,
        )
    with btn_col2:
        load_mongo = st.button(
            "MongoDB'den Yükle",
            disabled=st.session_state.scanning or not mongo_enabled,
            use_container_width=True,
        )
    with btn_col3:
        render_setup_expander()

    progress_bar = st.progress(0, text="Hazır")
    status_text = st.empty()

    if load_mongo:
        df_mongo = load_leads_from_mongo(secilen_sehir, mongo_uri, mongo_db)
        st.session_state.results = df_mongo
        st.session_state.last_sehir = secilen_sehir
        st.success(f"**{secilen_sehir}** koleksiyonundan **{len(df_mongo)}** kayıt yüklendi.")

    if start_scan:
        api_key = get_api_key(provider, sidebar_api_key)
        if not api_key:
            st.error("Lütfen geçerli bir API anahtarı girin (sol menü veya secrets.toml).")
        elif not anahtar_kelime.strip():
            st.error("Anahtar kelime boş olamaz.")
        else:
            st.session_state.scanning = True
            st.session_state.google_api_error_key = None
            st.session_state.place_cache = {}
            ilceler = TURKIYE_IL_ILCE[secilen_sehir]

            if provider == "Google Places API":
                referer = get_google_referer(sidebar_referer)
                place_cache = st.session_state.place_cache
                search_fn: Callable[[str], list[dict[str, str]]] = (
                    lambda q, k=api_key, r=referer, c=place_cache: search_google_places(q, k, r, c)
                )
            else:
                search_fn = lambda q: search_apify(q, api_key)

            progress_bar.progress(0, text="Tarama başlıyor...")
            with st.spinner("İlçeler taranıyor, lütfen bekleyin..."):
                df = scrape_city(
                    sehir=secilen_sehir,
                    anahtar_kelime=anahtar_kelime.strip(),
                    ilceler=ilceler,
                    search_fn=search_fn,
                    progress_bar=progress_bar,
                    status_text=status_text,
                )

            st.session_state.results = df
            st.session_state.last_sehir = secilen_sehir
            st.session_state.scanning = False
            progress_bar.progress(1.0, text="Tamamlandı")

            scan_count = len(df)
            mongo_eklenen = 0
            mongo_atlanan = 0
            mongo_hata = ""

            if mongo_enabled:
                mongo_stats = save_leads_to_mongo(
                    sehir=secilen_sehir,
                    leads=df.to_dict(orient="records"),
                    anahtar_kelime=anahtar_kelime.strip(),
                    mongo_uri=mongo_uri,
                    db_name=mongo_db,
                )
                if mongo_stats.get("durum") == "ok":
                    mongo_eklenen = int(mongo_stats.get("eklenen", 0))
                    mongo_atlanan = int(mongo_stats.get("atlanan", 0))
                    df_all = load_leads_from_mongo(secilen_sehir, mongo_uri, mongo_db)
                    st.session_state.results = df_all
                    scan_count = len(df_all)
                else:
                    mongo_hata = str(mongo_stats.get("mesaj", "Bilinmeyen hata"))

            mongo_info = (
                f"<div class='scan-status-meta'>MongoDB: {mongo_eklenen} yeni eklendi · "
                f"{mongo_atlanan} zaten kayıtlı · Toplam {scan_count} kayıt</div>"
                if mongo_enabled and not mongo_hata
                else (
                    f"<div class='scan-status-meta' style='color:#b45309;'>MongoDB hatası: {mongo_hata}</div>"
                    if mongo_hata
                    else ""
                )
            )

            status_text.markdown(
                f"""
                <div class="scan-status" style="border-left-color:#10b981;background:linear-gradient(90deg,#ecfdf5,#f0fdf4);border-color:#a7f3d0;">
                    <div class="scan-status-label" style="color:#047857;">Tarama Tamamlandı</div>
                    <div class="scan-status-title">{scan_count} kayıt</div>
                    <div class="scan-status-meta">{secilen_sehir} · {ilce_sayisi} ilçe tarandı</div>
                    {mongo_info}
                </div>
                """,
                unsafe_allow_html=True,
            )

    # Sonuçlar bölümü
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        """
        <div class="results-header">
            <div class="panel-title" style="margin:0;">Sonuçlar</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    df_results = st.session_state.results

    if df_results.empty:
        st.markdown(
            """
            <div class="panel empty-state">
                <div class="empty-state-icon">🔍</div>
                <div style="font-size:1.05rem;font-weight:600;color:#334155;margin-bottom:0.35rem;">
                    Henüz sonuç yok
                </div>
                <div>Şehir ve anahtar kelime seçip <strong>Taramayı Başlat</strong> butonuna tıklayın.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f'<div class="results-pill">✓ {len(df_results)} kayıt listeleniyor</div>',
            unsafe_allow_html=True,
        )

        st.dataframe(
            df_results,
            use_container_width=True,
            hide_index=True,
            column_config={
                COLUMN_FIRMA: st.column_config.TextColumn("Firma Adı", width="large"),
                COLUMN_TELEFON: st.column_config.TextColumn("Telefon Numarası", width="medium"),
            },
        )

        tarih = datetime.now().strftime("%Y%m%d_%H%M")
        sehir_slug = st.session_state.last_sehir or secilen_sehir
        base_name = f"leads_{sehir_slug}_{tarih}"
        leads_list = df_results.to_dict(orient="records")

        st.markdown("#### Dışa Aktar")
        export_col1, export_col2, export_col3 = st.columns([1, 1, 2])
        with export_col1:
            csv_buffer = io.BytesIO()
            csv_buffer.write(df_results.to_csv(index=False).encode("utf-8-sig"))
            st.download_button(
                label="CSV Olarak İndir",
                data=csv_buffer.getvalue(),
                file_name=f"{base_name}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with export_col2:
            txt_content = leads_to_txt(leads_list)
            st.download_button(
                label="TXT Olarak İndir",
                data=txt_content.encode("utf-8"),
                file_name=f"{base_name}.txt",
                mime="text/plain",
                use_container_width=True,
            )

    st.markdown(
        '<div class="footer-note">Lead Scraper · Türkiye işletme verisi toplayıcı · Kişisel kullanım</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
