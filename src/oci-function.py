import io
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from fdk import response
import oci

def handler(ctx, data: io.BytesIO=None):
    body = json.loads(data.getvalue())
    pool_ocid = body.get("poolOCID")
    qtd_request_per_vm = body.get("qtdRequestPerVM")
    signer = oci.auth.signers.get_resource_principals_signer()

    compartment_id = getCompartmentId(signer=signer, pool_ocid=pool_ocid)
    backendSetName = getBackendSetNameForPool(signer=signer, pool_ocid=pool_ocid)
     
    #asg_max_size = getMaxNumberInstances(signer=signer, compartment_id=compartment_id, pool_ocid=pool_ocid)
    pool_size = getCurrentPoolSize(pool_ocid, signer=signer)
    total_requests = getLoadBalancerRequestCount(backendSet=backendSetName, compartment_id=compartment_id, signer=signer)
    asg_max_size, asg_min_size = getAutoScalingSizes(signer, compartment_id, pool_ocid)
    
    new_pool_size = calculateNewPoolSize(total_requests, pool_size, qtd_request_per_vm, asg_max_size, asg_min_size)

    if new_pool_size > pool_size:
            update_pool_size(pool_ocid, new_pool_size, signer=signer)
            result = (f"Novo tamanho do pool definido: {new_pool_size}")
    elif new_pool_size < pool_size:
            update_pool_size(pool_ocid, new_pool_size, signer=signer)
            result = (f"Novo tamanho do pool definido: {new_pool_size}")
    else:
            result = ("Numero de requisicoes nao excede o limite para aumentar o pool.")
            
    return response.Response(ctx,
        response_data=json.dumps({"compartment_id": compartment_id,
                                  "backendSetName": backendSetName,
                                  "asg_max_size": asg_max_size,
                                  "asg_min_size": asg_min_size,
                                  "pool_size": pool_size,
                                  "total_requests": total_requests,
                                  "new_pool_size": new_pool_size,
                                  "result": result}),
        headers={"Content-Type": "application/json"} )

def getCompartmentId(signer, pool_ocid):
    # Get Compartment_ID --------------------------------------------------------
    compute_management_client = oci.core.ComputeManagementClient({}, signer=signer)
    try:
        response = compute_management_client.get_instance_pool(pool_ocid, retry_strategy=oci.retry.DEFAULT_RETRY_STRATEGY)
        compartment_id = response.data.compartment_id
    except Exception as e:
        compartment_id = str(e)
    #return {"compartment_id": compartment_id, }
    return compartment_id

def getBackendSetNameForPool(signer, pool_ocid):
    # Get Backend Name --------------------------------------------------------
    compute_management_client = oci.core.ComputeManagementClient({}, signer=signer)
    try:
        instance_pool_details = compute_management_client.get_instance_pool(instance_pool_id=pool_ocid, retry_strategy=oci.retry.DEFAULT_RETRY_STRATEGY).data
        if instance_pool_details.load_balancers:
            for lb_attachment in instance_pool_details.load_balancers:
                backend_set_name = lb_attachment.backend_set_name
                return backend_set_name
    except Exception as e:
        backend_set_name = str(e)
    return backend_set_name

def getMaxNumberInstances(signer, compartment_id, pool_ocid):
    autoscaling_client = oci.autoscaling.AutoScalingClient({}, signer=signer)

    try:
        list_response = autoscaling_client.list_auto_scaling_configurations(compartment_id, retry_strategy=oci.retry.DEFAULT_RETRY_STRATEGY)
        for autoscaling_config in list_response.data: 
            resource = autoscaling_config.resource.id
            if resource == pool_ocid:
                asg_max_size = autoscaling_client.get_auto_scaling_configuration(auto_scaling_configuration_id=autoscaling_config.id, retry_strategy=oci.retry.DEFAULT_RETRY_STRATEGY).data.max_resource_count
                return asg_max_size
    except oci.exceptions.ServiceError as e:
        asg_max_size = str(e)
    return asg_max_size

def getCurrentPoolSize(pool_ocid, signer):
    compute_client = oci.core.ComputeManagementClient({}, signer=signer)
    try:
        instance_pool = compute_client.get_instance_pool(instance_pool_id=pool_ocid, retry_strategy=oci.retry.DEFAULT_RETRY_STRATEGY).data.size 
    except Exception as e:
        instance_pool = str(e)
    return instance_pool


def getLoadBalancerRequestCount(backendSet, compartment_id, signer):
    monitoring_client = oci.monitoring.MonitoringClient({}, signer=signer)
    try:
        end_time = datetime.now(timezone.utc).isoformat('T')
        start_time = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat('T')

        m_metric = oci.monitoring.models.SummarizeMetricsDataDetails(
            end_time=end_time,
            start_time=start_time,
            namespace="oci_lbaas",
            query=f"HttpRequests[1m]{{backendSetName= {backendSet}}}.grouping().max()"
            
        )

        response = monitoring_client.summarize_metrics_data(
            compartment_id=compartment_id,
            summarize_metrics_data_details=m_metric,
            retry_strategy=oci.retry.DEFAULT_RETRY_STRATEGY
           )

        # Extração direta do valor desejado
        getRequestSummarizedMetric = json.loads(str(response.data))
        
        if not getRequestSummarizedMetric or 'aggregated_datapoints' not in getRequestSummarizedMetric[0]:
            raise ValueError("Nenhum dado de métrica encontrado ou formato de dados inválido.")

        return getRequestSummarizedMetric[0]['aggregated_datapoints'][0]['value']
        
    except Exception as e:
        print(f"Erro ao obter dados de métricas: {e}")
        return None  # Retorna None em caso de erro para tratamento posterior
    
def calculateNewPoolSize(qtd_requests, pool_size, qtd_request_per_vm, asg_max_size, asg_min_size):
    if (qtd_requests / pool_size) > qtd_request_per_vm and pool_size < asg_max_size:
        new_pool_size = qtd_requests // qtd_request_per_vm
        return min(new_pool_size, asg_max_size)
    elif (qtd_requests / pool_size) < qtd_request_per_vm and pool_size > asg_min_size:
        new_pool_size = qtd_requests // qtd_request_per_vm
        return max(new_pool_size, asg_min_size)
    return pool_size

def update_pool_size(pool_ocid, new_size, signer):
    compute_client = oci.core.ComputeManagementClient({}, signer=signer)
    try:
        update_details = oci.core.models.UpdateInstancePoolDetails(size=new_size)
        response = compute_client.update_instance_pool(instance_pool_id=pool_ocid, update_instance_pool_details=update_details)
        return response.data
    except oci.exceptions.ServiceError as e:
        return None

def getAutoScalingSizes(signer, compartment_id, pool_ocid):
    autoscaling_client = oci.autoscaling.AutoScalingClient({}, signer=signer)

    try:
        list_response = autoscaling_client.list_auto_scaling_configurations(compartment_id, retry_strategy=oci.retry.DEFAULT_RETRY_STRATEGY)
        for autoscaling_config in list_response.data: 
            resource = autoscaling_config.resource.id
            if resource == pool_ocid:
                config = autoscaling_client.get_auto_scaling_configuration(auto_scaling_configuration_id=autoscaling_config.id, retry_strategy=oci.retry.DEFAULT_RETRY_STRATEGY).data
                asg_max_size = config.max_resource_count
                asg_min_size = config.min_resource_count
                return asg_max_size, asg_min_size
    except oci.exceptions.ServiceError as e:
        return str(e), None
    return None, None