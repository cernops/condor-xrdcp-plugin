%if %{rhel} >= 7
%{!?dist: %define dist .el7}
%else
%{!?dist: %define dist .el6}
%endif

Name: condor-xrdcp-plugin
Version: 0.1.4
Release: 1%{?dist}
Summary:	HTCondor file transfer plugin for XRootD

Group:		System Environment/Base
License:	Apache License 2.0
URL:        https://gitlab.cern.ch/batch-team/condor-xrdcp-plugin
BuildRoot:	%(mktemp -ud %{_tmppath}/%{name}-%{version}-%{release}-XXXXXX)
Source0:         %{name}-%{version}.tar.gz


%global py_version python3
%define __python /usr/bin/python3
BuildRequires: python3-devel
Requires: python3-condor, condor


%define debug_package %{nil}
%description


%prep
%setup -q

%build


%install
%{__rm} -rf %{buildroot}
mkdir -p ${RPM_BUILD_ROOT}/usr/libexec/condor/
install -m 755 src/xrdcp_plugin.py ${RPM_BUILD_ROOT}/usr/libexec/condor/

%clean
rm -rf ${RPM_BUILD_ROOT}

%post
/usr/sbin/condor_reconfig > /dev/null 2>&1

%files
%defattr(-,root,root,-)
/usr/libexec/condor/xrdcp_plugin.py
%if 0%{?el7}
/usr/libexec/condor/__pycache__/*.pyc
%endif


%changelog
* Fri Jun 21 2024 Ben Jones <b.jones@cern.ch> - 0.1.4-1
- Add license files for GH publish
* Thu Mar 03 2022 Ben Jones <b.jones@cern.ch> - 0.1.3-1
- limit error size.
* Mon Feb 14 2022 Ben Jones <b.jones@cern.ch> - 0.1.2-1
- xrdcp options
* Mon Feb 14 2022 Ben Jones <b.jones@cern.ch> - 0.1.1-2
- spec file
* Mon Feb 14 2022 Ben Jones <b.jones@cern.ch> - 0.1.1-1
- Moved to correct libexec location
- Job classads need to be namespaced to avoid clobbering on starter
* Wed Feb 09 2022 Ben Jones <b.jones@cern.ch> - 0.1.0-1
- Initial release
