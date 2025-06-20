import frappe
import stripe
from frappe.auth import LoginManager
from frappe.utils.password import update_password


@frappe.whitelist(allow_guest=False)
def deduct_credits(user,trainer):
    wallet = frappe.get_doc("Credits", {"user": user})
    if wallet.credits >= 10:
        wallet.credits = wallet.credits - 10
        wallet.save()

        frappe.get_doc({
            "doctype": "Credit Transaction",
            "user": user,
            "transaction_type": "Usage",
            "credits": -10,
	    "reference_trainer":trainer
        }).insert()

        frappe.get_doc({
	    "doctype":"Unlocked Trainers",
	    "user":user,
	    "trainer":trainer
	}).insert()

        return {"success": True, "message": "success"}
    else:
        return {"success": False, "message": "Not enough credits. Please purchase more."}
    


stripe.api_key = frappe.conf.get("stripe_secret_key")

@frappe.whitelist()
def create_checkout_session(amount):
    user = frappe.session.user
    # amount = frappe.form_dict.get("amount")
    amount=int(amount)
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "product_data": {
                            "name": "Credits Purchase",
                        },
                        "unit_amount": int(amount)*100//5,
                    },
                    "quantity": 1,
                },
            ],
            mode="payment",
            success_url=f"http://trainer.localhost:8000/payment_success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"http://trainer.localhost:8000/payment-failed",
        )
        return {"session_id": checkout_session.id, "redirect_url": checkout_session.url}
    except Exception as e:
        frappe.log_error(f"Stripe Error: {str(e)}", "Payment Error")
        frappe.throw("Unable to create payment session. Please try again.")

@frappe.whitelist(allow_guest=True)
def payment_success(session_id):
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        if session.payment_status == "paid":
            user = frappe.session.user
            amount = session.amount_total // 50
            user_doc = frappe.get_all("Credits", filters={"user": user}, fields=["name","user", "credits"])

            if user_doc:
                credits_doc = frappe.get_doc("Credits", user_doc[0].get("name"))
                credits_doc.credits = credits_doc.credits + int(amount)
                credits_doc.save(ignore_permissions=True)  # Save changes

                transaction = frappe.get_doc({
                    "doctype": "Credit Transaction",  # Ensure this is the correct Doctype name
                    "user": user,
                    "transaction_type": "Purchase",
                    "credits": int(amount),  # Ensure amount is properly converted
                    "amount": session.amount_total / 100,  # Convert from paise to INR
                    "reference_trainer": None  # Explicitly setting to None
                })
                transaction.insert(ignore_permissions=True)

                frappe.db.commit()

                frappe.msgprint("Payment successful! Credits updated.")
                return {"status": "success", "message": "Credits added successfully"}
            else:
                return {"status": "failed", "message": "User not found in Credits Doctype"}

        else:
            return {"status": "failed", "message": "Payment not successful"}
    except Exception as e:
        frappe.log_error(f"Payment Success Error: {str(e)}", "Payment Error")
        return {"status": "failed", "message": "An error occurred."}


@frappe.whitelist(allow_guest=True)
def signup_trainer(email, first_name, password, last_name=None, roles=None):
    if not email or not first_name or not password:
        return {"status": "error", "message": "Email, First Name, and Password are required"}

    # Check if the user already exists
    existing_user = frappe.get_all("User", filters={"email": email})
    if existing_user:
        return {"status": "error", "message": "User with this email already exists"}
    if roles==None:
        roles=["Trainer"]
    # Create a new user document
    user_doc = frappe.get_doc({
        "doctype": "User",
        "email": email,
        "first_name": first_name,
	    "last_name":last_name,
        "enabled": 1,
        "role_user": "Trainer",
        "new_password": password,
        "roles": [{"role": role} for role in roles],
    })

    try:
        # Insert the user document into the database
        user_doc.insert(ignore_permissions=True)

        update_password(user=email, pwd=password)

        # Send welcome email or other post-signup actions can be triggered here.
        #if user_doc:
        #	generate_otp(email)
#            subject="Welcome to our Platform",
#            message="Hello, {}! Welcome to our platform.".format(first_name)
#        )
        
        return {"status": "success", "message": "User created successfully", "user": user_doc, "key_details":generate_key(email)}

    except Exception as e:
        frappe.log_error(f"Error creating user: {str(e)}", "Custom Signup Error")
        return {"status": "error", "message": "Error creating user: {}".format(str(e))}

@frappe.whitelist(allow_guest=True)
def signup_User(email, first_name, password, last_name=None, roles=None):
    if not email or not first_name or not password:
        return {"status": "error", "message": "Email, First Name, and Password are required"}

    # Check if the user already exists
    existing_user = frappe.get_all("User", filters={"email": email})
    if existing_user:
        return {"status": "error", "message": "User with this email already exists"}
    if roles==None:
        roles=["user_role"]
    # Create a new user document
    user_doc = frappe.get_doc({
        "doctype": "User",
        "email": email,
        "first_name": first_name,
	    "last_name":last_name,
        "enabled": 1,
        "role_user": "user_role",
        "new_password": password,
        "roles": [{"role": role} for role in roles],
    })

    try:
        # Insert the user document into the database
        user_doc.insert(ignore_permissions=True)

        update_password(user=email, pwd=password)

        # Send welcome email or other post-signup actions can be triggered here.
        #if user_doc:
        #	generate_otp(email)
#            subject="Welcome to our Platform",
#            message="Hello, {}! Welcome to our platform.".format(first_name)
#        )
        
        return {"status": "success", "message": "User created successfully", "user": user_doc, "key_details":generate_key(email)}

    except Exception as e:
        frappe.log_error(f"Error creating user: {str(e)}", "Custom Signup Error")
        return {"status": "error", "message": "Error creating user: {}".format(str(e))}


@frappe.whitelist(allow_guest = True)
def customLogin(usr,pwd):
	login_manager = LoginManager()
	login_manager.authenticate(usr,pwd)
	login_manager.post_login()
#	print(frappe.response)
	if frappe.response['message'] == 'Logged In' or 'No App':
		user = login_manager.user
#		print(user)
		frappe.response['key_details'] = generate_key(user)
		frappe.response['user_details'] = get_user_details(user)
          
	else:
		return False
	
def generate_key(user):
	user_details = frappe.get_doc("User", user)
	api_secret = api_key = ''
	if not user_details.api_key and not user_details.api_secret:
		api_secret = frappe.generate_hash(length=15)
		api_key = frappe.generate_hash(length=15)
		user_details.api_key = api_key
		user_details.api_secret = api_secret
		user_details.save(ignore_permissions = True)
	else:
		api_secret = user_details.get_password('api_secret')
		api_key = user_details.get('api_key')
	return {"api_secret": api_secret,"api_key": api_key}

def get_user_details(user):
	print(user)
	user_details = frappe.get_all("User",filters={"name":user},fields=["name","first_name","last_name","email","role_user","last_login"])
	if user_details:
		return user_details[0]

@frappe.whitelist(allow_guest=True)
def get_all_trainers(user, page=1, page_size=10):
    """Fetch paginated trainers sorted by avg_review (desc)"""
    page = int(page)
    page_size = int(page_size)
    start = (page - 1) * page_size  # Calculate the offset

    # Ensure we fetch trainer names explicitly
    query = """
        SELECT 
            t.trainer,
            t.full_name, 
            t.name,
            t.first_name,
            t.last_name, 
            t.cover_image, 
            t.image, 
            t.avg_rating,
            t.location,
            t.charge,
            CASE 
                WHEN w.trainers IS NOT NULL THEN 1 
                ELSE 0 
            END AS is_wishlisted,
            CASE 
                WHEN u.trainer IS NOT NULL THEN 1 
                ELSE 0 
            END AS is_unlocked
        FROM tabTrainer t
        LEFT JOIN tabWishlist w ON w.trainers = t.trainer AND w.users = %(user)s
        LEFT JOIN `tabUnlocked Trainers` u ON u.trainer = t.trainer AND u.user = %(user)s
        ORDER BY t.avg_rating DESC
        LIMIT %(start)s, %(page_size)s
    """

    trainers = frappe.db.sql(
        query,
        {"user": user, "start": start, "page_size": page_size},
        as_dict=True
    )

    # Step 2: Fetch all expertise for the trainers
    trainer_ids = [trainer["trainer"] for trainer in trainers]

    for trainer in trainers:
        if frappe.db.exists("Trainer", trainer["name"]):
            result = frappe.get_doc("Trainer", trainer["name"])
            # Extract expertise as a list of strings
            trainer["expertise_in"] = result.expertise_in
        else:
            trainer["expertise_in"] = []

    # Get wishlist trainers for the current user
    wishlist_trainers = frappe.db.get_all(
        "Wishlist",
        filters={"users": user},
        fields=["*"]
    )
    wishlist_trainer_ids = {entry["trainers"] for entry in wishlist_trainers}

    # Get unlocked trainers for the current user
    unlocked_trainers = frappe.db.get_all(
        "Unlocked Trainers",
        filters={"user": user},
        fields=["*"]
    )
    unlocked_trainer_ids = {entry["trainer"] for entry in unlocked_trainers}

    # Mark trainers as wishlisted and unlocked
    for trainer in trainers:
        trainer_id = trainer["name"]  # Use 'name' instead of 'trainer'
        trainer["is_wishlisted"] = 1 if trainer_id in wishlist_trainer_ids else 0
        trainer["is_unlocked"] = 1 if trainer_id in unlocked_trainer_ids else 0

    for trainer in unlocked_trainers:
        trainer_id = trainer["trainer"]
        trainer["is_wishlisted"] = 1 if trainer_id in wishlist_trainer_ids else 0

    unlocked=[]
    for trainer in trainers:
         if trainer["is_unlocked"]:
              unlocked.append(trainer)

    locked=[]
    for trainer in trainers:
         if trainer["is_unlocked"] == 0:
              locked.append(trainer)

    wishlist=[]
    for trainer in trainers:
         if trainer["is_wishlisted"]:
              wishlist.append(trainer)

    # Get total count for pagination
    total_count = frappe.db.count("Trainer")

    return {
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "All_trainers": locked,
        "unlocked_trainers": unlocked,
        "wishlist_trainers": wishlist
    }



@frappe.whitelist()
def search_trainers(search_text=None, location=None, expertise=None, sort_by="rating", order="desc", page=1, page_size=10):
    """
    Search trainers based on full_name, expertise, and location.
    Filters: location, expertise.
    Sorting: price (high to low, low to high), rating (high to low, low to high).
    """
    page = int(page)
    page_size = int(page_size)
    start = (page - 1) * page_size

    # Base SQL query
    query = """
        SELECT 
            t.trainer, t.full_name, t.location, t.charge, t.avg_rating, t.cover_image, t.image,
            GROUP_CONCAT(DISTINCT e.expertise ORDER BY e.expertise SEPARATOR ', ') AS expertise
        FROM tabTrainer t
        LEFT JOIN tabExpertise e ON e.trainer = t.name
        WHERE 1=1
    """
    
    filters = {}
    
    # Apply location filter
    if location:
        query += " AND t.location = %(location)s"
        filters["location"] = location

    # Apply search query (searching in full_name and expertise)
    if search_text:
        query += " AND t.full_name LIKE %(search_text)s"
        filters["search_text"] = f"%{search_text}%"

    if expertise:
        query += " AND e.expertise LIKE %(expertise)s"
        filters["expertise_in"] = f"%{expertise}%"

    # Sorting options
    sort_column = "t.avg_rating" if sort_by == "rating" else "t.charge"
    sort_order = "DESC" if order == "desc" else "ASC"
    query += f" ORDER BY {sort_column} {sort_order}"

    # Pagination
    query += " LIMIT %(page_size)s OFFSET %(start)s"
    filters["page_size"] = page_size
    filters["start"] = start

    # Execute query
    trainers = frappe.db.sql(query, filters, as_dict=True)

    # Get total count for pagination
    count_query = """
        SELECT COUNT(DISTINCT t.trainer) AS total
        FROM tabTrainer t
        LEFT JOIN tabExpertise_in e ON e.trainer = t.trainer
        WHERE 1=1
    """
    if location:
        count_query += " AND t.location = %(location)s"
    if search_text:
        count_query += " AND t.full_name LIKE %(search_text)s"
    if expertise:
        count_query += " AND e.expertise LIKE %(expertise)s"

    total_count = frappe.db.sql(count_query, filters, as_dict=True)[0]["total"]

    return {
        "total": total_count,
        "page": page,
        "page_size": page_size,
        "trainers": trainers
    }