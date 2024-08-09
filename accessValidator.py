
from xray_service import getStatusXrayCloud

def accessValidator():
    error = 0
    print("****************VALIDANDO accesos**********************")

    #[Xray Cloud GraphQL]
    try:
        print("...VALIDANDO [Xray Cloud GraphQL]...")
        getStatusXrayCloud()
        print(f"    STATUS:[Xray Cloud GraphQL] Acceso Validado ")      
    except Exception as e: 
        print(f"    STATUS:[Xray Cloud GraphQL] ERROR: ${e}")
        error += 1
    print("----------------------------------------------------------------")
  
    return error
