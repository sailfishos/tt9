Name:       tt9
Summary:    Keypad layouts and predictive dictionaries for Sailfish OS
Version:    1.0
Release:    1
License:    Apache-2.0 and MIT and BSD-3-Clause and GPL-2.0-or-later and GPL-2.0-only and GPL-3.0-only and LGPL-2.1-or-later and LGPL-2.1-only and LGPL-3.0-only and AGPL-3.0-only and MPL-1.1 and MPL-2.0 and CC0-1.0 and CC-BY-3.0 and CC-BY-4.0 and CC-BY-SA-4.0 and ODbL-1.0 and LicenseRef-CLARIN-PUB-BY and LicenseRef-Database-Contents and LicenseRef-GFDL-Unverified and LicenseRef-Public-Domain and LicenseRef-Unresolved
BuildArch:  noarch
URL:        https://github.com/sailfishos/tt9
Source0:    %{name}-%{version}.tar.bz2
BuildRequires: python3-base
BuildRequires: python3-sqlite

%description
Keypad layouts from Traditional T9, one locale layout file per language, plus
word lists for the locales named in dictionaries.list. The Sailfish OS keypad
reads both from %{_datadir}/keypad. A layout is enough for the letters.
Prediction needs the matching sqlite file.

%package layouts
Summary:    Keypad layouts from Traditional T9
License:    Apache-2.0

%description layouts
Keypad layouts from Traditional T9 for Sailfish OS.

%package dictionary-ar-jo
Summary:    Keypad dictionary for ar-JO from Traditional T9
License:    ODC-BY
Requires:   %{name}-layouts

%description dictionary-ar-jo
Word list for ar-JO from Traditional T9, for keypad prediction.

%package dictionary-de-de
Summary:    Keypad dictionary for de-DE from Traditional T9
License:    GPL-2.0-or-later
Requires:   %{name}-layouts

%description dictionary-de-de
Word list for de-DE from Traditional T9, for keypad prediction.

%package dictionary-en
Summary:    Keypad dictionary for en from Traditional T9
License:    GPL
Requires:   %{name}-layouts

%description dictionary-en
Word list for en from Traditional T9, for keypad prediction.

%package dictionary-es-es
Summary:    Keypad dictionary for es-ES from Traditional T9
License:    ODC-BY
Requires:   %{name}-layouts

%description dictionary-es-es
Word list for es-ES from Traditional T9, for keypad prediction.

%package dictionary-fi-fi
Summary:    Keypad dictionary for fi-FI from Traditional T9
License:    GPL-3.0-only
Requires:   %{name}-layouts 

%description dictionary-fi-fi
Word list for fi-FI from Traditional T9, for keypad prediction.

%package dictionary-fr-fr
Summary:    Keypad dictionary for fr-FR from Traditional T9
License:    MIT and CC BY-SA 4.0 and MPL 2.0
Requires:   %{name}-layouts

%description dictionary-fr-fr
Word list for fr-FR from Traditional T9, for keypad prediction.

%package dictionary-hi-in
Summary:    Keypad dictionary for hi-IN from Traditional T9
License:    GPL
Requires:   %{name}-layouts

%description dictionary-hi-in
Word list for hi-IN from Traditional T9, for keypad prediction.

%package dictionary-it-it
Summary:    Keypad dictionary for it-IT from LibreOffice
License:    GPL-3.0-only
Requires:   %{name}-layouts

%description dictionary-it-it
Word list for it-IT from the LibreOffice it_IT dictionary, for keypad prediction.

%package dictionary-nb-no
Summary:    Keypad dictionary for nb-NO from LibreOffice
License:    GPL-2.0-only and CC-BY-4.0 and LicenseRef-CLARIN-PUB-BY
Requires:   %{name}-layouts

%description dictionary-nb-no
Word list for nb-NO from the LibreOffice Norwegian dictionary, for keypad prediction.

%package dictionary-pt-pt
Summary:    Keypad dictionary for pt-PT from LibreOffice
License:    GPL-2.0-only OR LGPL-2.1-only OR MPL-1.1
Requires:   %{name}-layouts

%description dictionary-pt-pt
Word list for pt-PT from the LibreOffice pt_PT dictionary, for keypad prediction.

%package dictionary-zh-cn
Summary:    Keypad dictionary for zh-CN from Traditional T9
License:    CC BY 4.0
Requires:   %{name}-layouts

%description dictionary-zh-cn
Word list for zh-CN from Traditional T9, for keypad prediction.

%prep
%autosetup -n %{name}-%{version}

%build
python3 build-dictionaries.py --output tt9-data --notices tt9-notices \
    --from-list languages.list --dictionaries dictionaries.list

%install
mkdir -p %{buildroot}%{_datadir}/keypad
cp -a tt9-data/. %{buildroot}%{_datadir}/keypad/

%files layouts
%license tt9/LICENSE.txt
%dir %{_datadir}/keypad
%{_datadir}/keypad/*.layout

%files dictionary-ar-jo
%%license tt9-notices/ar-JO.txt tt9-notices/ar-JO.license
%{_datadir}/keypad/ar-JO.sqlite

%files dictionary-de-de
%%license tt9-notices/de-DE.txt tt9-notices/de-DE.license
%{_datadir}/keypad/de-DE.sqlite

%files dictionary-en
%%license tt9-notices/en.txt tt9-notices/en.license
%{_datadir}/keypad/en.sqlite

%files dictionary-es-es
%%license tt9-notices/es-ES.txt tt9-notices/es-ES.license
%{_datadir}/keypad/es-ES.sqlite

%files dictionary-fi-fi
%%license tt9-notices/fi-FI.txt tt9-notices/fi-FI.license
%{_datadir}/keypad/fi-FI.sqlite

%files dictionary-fr-fr
%%license tt9-notices/fr-FR.txt tt9-notices/fr-FR.license
%{_datadir}/keypad/fr-FR.sqlite

%files dictionary-hi-in
%%license tt9-notices/hi-IN.txt tt9-notices/hi-IN.license
%{_datadir}/keypad/hi-IN.sqlite

%files dictionary-it-it
%%license tt9-notices/it-IT.txt tt9-notices/it-IT.license
%{_datadir}/keypad/it-IT.sqlite

%files dictionary-nb-no
%%license tt9-notices/nb-NO.txt tt9-notices/nb-NO.license
%{_datadir}/keypad/nb-NO.sqlite

%files dictionary-pt-pt
%%license tt9-notices/pt-PT.txt tt9-notices/pt-PT.license
%{_datadir}/keypad/pt-PT.sqlite

%files dictionary-zh-cn
%%license tt9-notices/zh-CN.txt tt9-notices/zh-CN.license
%{_datadir}/keypad/zh-CN.sqlite
