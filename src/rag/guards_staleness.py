def staleness_guard(source_date_str: Optional[str], max_age_days: int = 365) -> Tuple[bool, str]:
    """
    Check if a source is too old based on its date.
    
    Args:
        source_date_str: Date string in 'YYYY-MM-DD' format or None
        max_age_days: Maximum acceptable age in days (default: 365)
        
    Returns:
        Tuple of (passed, message) where passed is True if the guard passes
    """
    if not source_date_str:
        logger.warning("No source date provided for staleness check")
        return False, "Source date is missing"
    
    try:
        # Parse the date string
        source_date = datetime.datetime.strptime(source_date_str, "%Y-%m-%d").date()
        
        # Calculate the age in days
        today = datetime.datetime.now().date()
        age_days = (today - source_date).days
        
        if age_days > max_age_days:
            return False, f"Source is {age_days} days old, exceeding the maximum age of {max_age_days} days"
        else:
            return True, f"Source is {age_days} days old, within the acceptable range of {max_age_days} days"
    
    except ValueError as e:
        logger.error(f"Error parsing source date '{source_date_str}': {str(e)}")
        return False, f"Invalid source date format: {source_date_str}"
