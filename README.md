# cvc-pool-size-changer-func
Serviço Python para OCI Funcion utlizado para alterar o tamanho do pool de requisições de serviços.

## Módulos
- `oci-function.py`: Versão que deve ser executada na Function do OCI.
- `retry-test.py`: Versão de teste local que importa o certificado de autenticação.
- `test_function.py`: Arquivo que inicia o projeto local e passa por json as informações para o módulo retry-test.

## JSON necessário
- OCID: ID do loadbalancer que será alterado.
- PoolOCID: ID do pool de instâncias.
- qtdRequestPerVM: Quantidade de requisições recebidas por máquinas virtuais.

## How to run...
- Local: python test_function.py
- OCI: Copiar e colar o código do módulo oci-function.py na Function do OCI.
