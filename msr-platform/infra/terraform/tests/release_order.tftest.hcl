# Orden temporal entre la AMI base y la release que corrige el advisory.
#
# Evalúan la expresión real (no una búsqueda de texto) sin contactar con AWS:
# el provider está simulado y los recursos no se crean en ningún caso.

mock_provider "aws" {}

variables {
  enable_real_resources = false
}

run "the_real_values_place_the_ami_before_the_fix" {
  command = plan

  assert {
    condition     = output.release_order.source_ami_date == 20260509
    error_message = "La fecha de la AMI base debe extraerse como número (20260509)."
  }

  assert {
    condition     = output.release_order.candidate_date == 20260706
    error_message = "La fecha de la corrección debe extraerse como número (20260706)."
  }

  assert {
    condition     = output.release_order.amazon_linux_2023
    error_message = "Ambas releases deben ser de Amazon Linux 2023."
  }

  assert {
    condition     = output.release_order.ami_precedes_fix
    error_message = "20260509 < 20260706 debe evaluarse como cierto."
  }
}

run "the_same_date_is_rejected" {
  command = plan

  variables {
    source_ami_release   = "2023.12.20260706.0"
    candidate_releasever = "2023.12.20260706"
  }

  assert {
    condition     = output.release_order.ami_precedes_fix == false
    error_message = "Una AMI publicada el mismo día que la corrección no es vulnerable."
  }
}

run "a_newer_ami_is_rejected" {
  command = plan

  variables {
    source_ami_release   = "2023.12.20260801.0"
    candidate_releasever = "2023.12.20260706"
  }

  assert {
    condition     = output.release_order.ami_precedes_fix == false
    error_message = "Una AMI posterior a la corrección ya contendría el parche."
  }
}

# La comparación no puede ser lexicográfica: "2023.11.20260509" > "2023.12.2026"
# como texto en cuanto cambian las longitudes, pero la fecha manda.
run "the_comparison_is_not_lexicographic" {
  command = plan

  variables {
    source_ami_release   = "2023.09.20261231.0"
    candidate_releasever = "2023.10.20270105"
  }

  assert {
    condition     = output.release_order.ami_precedes_fix
    error_message = "El orden debe derivarse de la fecha YYYYMMDD, no del texto."
  }
}

run "an_invalid_release_format_is_rejected" {
  command = plan

  variables {
    candidate_releasever = "2023.12"
  }

  expect_failures = [var.candidate_releasever]
}

run "an_invalid_ami_release_format_is_rejected" {
  command = plan

  variables {
    source_ami_release = "20260509"
  }

  expect_failures = [var.source_ami_release]
}
