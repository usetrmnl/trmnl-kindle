# ----------------------------- UTILITY FUNCTIONS -------------------------------- #
get_kindle_battery() {                                                                    
  # Run the command and capture its output                                                
  local result=$(lipc-get-prop com.lab126.powerd status)                                  
                                                                                          
  # Extract the battery level using grep and cut                                          
  # Find the line with "Battery Level", extract just the percentage number                
  local battery_level=$(echo "$result" | grep "Battery Level:" | cut -d ":" -f2 | tr -d '% ')
                                                                                          
  # Return just the number                                                                
  echo "$battery_level"                                                                   
}                                                                                         
                                                                                          
get_kindle_width() {                                                                      
  # Run the command and capture its output                                                
  local result=$(eips -i)                                                                 
                                                                                          
  # Extract xres using grep and awk                                                       
  local xres=$(echo "$result" | grep "xres:" | head -1 | awk '{print $2}')                
                                                                                          
  # Return just the width value                                                           
  echo "$xres"                                                                            
}                                                                                         
                                                                                          
get_kindle_height() {                                                                     
  # Run the command and capture its output                                                
  local result=$(eips -i)                                                                 
                                                                                          
  # Extract yres using grep and awk                                                       
  local yres=$(echo "$result" | grep "yres:" | head -1 | awk '{print $4}')                
                                                                                          
  # Return just the height value                                                          
  echo "$yres"                                                                            
}      