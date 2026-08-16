# VCN + 인터넷 게이트웨이 + 라우트 + 보안 리스트 + 퍼블릭 서브넷
# 단일 노드 k3s가 퍼블릭 서브넷에 뜨고, 호스트는 공인 IP:6443으로 API에 접근한다.

resource "oci_core_vcn" "k3s" {
  compartment_id = var.compartment_ocid
  cidr_blocks    = [var.vcn_cidr]
  display_name   = "${var.name_prefix}-vcn"
  dns_label      = "k3svcn"
}

resource "oci_core_internet_gateway" "k3s" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.k3s.id
  display_name   = "${var.name_prefix}-igw"
}

resource "oci_core_route_table" "k3s" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.k3s.id
  display_name   = "${var.name_prefix}-rt"

  route_rules {
    destination       = "0.0.0.0/0"
    destination_type  = "CIDR_BLOCK"
    network_entity_id = oci_core_internet_gateway.k3s.id
  }
}

resource "oci_core_security_list" "k3s" {
  compartment_id = var.compartment_ocid
  vcn_id         = oci_core_vcn.k3s.id
  display_name   = "${var.name_prefix}-sl"

  # 아웃바운드 전체 허용
  egress_security_rules {
    destination = "0.0.0.0/0"
    protocol    = "all"
  }

  # SSH (22)
  ingress_security_rules {
    protocol = "6" # TCP
    source   = var.allowed_ssh_cidr
    tcp_options {
      min = 22
      max = 22
    }
  }

  # Kubernetes API (6443)
  ingress_security_rules {
    protocol = "6"
    source   = var.allowed_api_cidr
    tcp_options {
      min = 6443
      max = 6443
    }
  }

  # VCN 내부 전체 허용(노드·파드 통신). 단일 노드라도 향후 노드 추가 대비 관례적으로 둔다.
  ingress_security_rules {
    protocol = "all"
    source   = var.vcn_cidr
  }

  # Path MTU discovery(ICMP fragmentation-needed) 허용 — 연결 끊김 방지
  ingress_security_rules {
    protocol = "1" # ICMP
    source   = "0.0.0.0/0"
    icmp_options {
      type = 3
      code = 4
    }
  }
}

resource "oci_core_subnet" "k3s" {
  compartment_id             = var.compartment_ocid
  vcn_id                     = oci_core_vcn.k3s.id
  cidr_block                 = var.subnet_cidr
  display_name               = "${var.name_prefix}-subnet"
  route_table_id             = oci_core_route_table.k3s.id
  security_list_ids          = [oci_core_security_list.k3s.id]
  dns_label                  = "k3ssubnet"
  prohibit_public_ip_on_vnic = false
}
