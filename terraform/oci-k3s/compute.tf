# A1 Flex(ARM) 단일 인스턴스 + cloud-init로 k3s 설치.
# 주의: Always Free A1은 리전/AD별로 용량 부족(Out of host capacity, 500)이 잦다.
#       apply가 용량 오류로 실패하면 다른 AD/리전으로 재시도하거나 잠시 후 다시 apply 한다.

# 가용 도메인 목록(테넌시 루트 기준)
data "oci_identity_availability_domains" "ads" {
  compartment_id = var.tenancy_ocid
}

# shape에 맞는 최신 Ubuntu ARM 이미지 조회
data "oci_core_images" "ubuntu" {
  compartment_id           = var.compartment_ocid
  operating_system         = var.operating_system
  operating_system_version = var.operating_system_version
  shape                    = var.instance_shape
  sort_by                  = "TIMECREATED"
  sort_order               = "DESC"
}

resource "oci_core_instance" "k3s" {
  availability_domain = var.availability_domain != "" ? var.availability_domain : data.oci_identity_availability_domains.ads.availability_domains[0].name
  compartment_id      = var.compartment_ocid
  display_name        = "${var.name_prefix}-server"
  shape               = var.instance_shape

  shape_config {
    ocpus         = var.instance_ocpus
    memory_in_gbs = var.instance_memory_gbs
  }

  create_vnic_details {
    subnet_id        = oci_core_subnet.k3s.id
    assign_public_ip = true
    hostname_label   = "k3s"
  }

  source_details {
    source_type             = "image"
    source_id               = data.oci_core_images.ubuntu.images[0].id
    boot_volume_size_in_gbs = var.boot_volume_gbs
  }

  metadata = {
    ssh_authorized_keys = file(var.ssh_public_key_path)
    user_data = base64encode(templatefile("${path.module}/cloud-init.yaml.tftpl", {
      k3s_version = var.k3s_version
    }))
  }
}
